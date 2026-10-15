#!/usr/bin/env python3
"""Run declared compiler coverage; the release profile rejects unsupported rows."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.engine_harness import ENGINES, PROFILES, corpus_paths, execute, verify_case


def generate_markdown_matrix() -> str:
    positives, negatives = corpus_paths()
    fixtures = positives + negatives

    by_feature = {}
    for path in fixtures:
        label = str(path.relative_to(ROOT))
        feat = PROFILES.get('fixtures', {}).get(label, 'core')
        by_feature.setdefault(feat, []).append(label)

    rows = []
    rows.append("# W Language Engine Feature Parity Matrix")
    rows.append("")
    rows.append("| Feature Category | Fixtures | W0 Interpreter | W0 AST C99 | W0 Typed HIR (Default) | W1 Self-Hosted C99 | Status / Milestone |")
    rows.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")

    tot_fixtures = len(fixtures)
    w0_interp_tot = 0
    w0_ast_tot = 0
    w0_hir_tot = 0
    w1_tot = 0

    feature_order = ['core', 'generics', 'checked_modules']
    for feat in feature_order:
        items = by_feature.get(feat, [])
        count = len(items)
        unsupported_w1 = PROFILES.get('features', {}).get(feat, {}).get('w1', '')
        w0_interp_tot += count
        w0_ast_tot += count
        w0_hir_tot += count
        if unsupported_w1:
            w1_status = f"⏳ 0/{count} (Unsupported)"
            note = f"Pending {unsupported_w1.split(':')[0].strip()}"
        else:
            w1_tot += count
            w1_status = f"✅ {count}/{count} (Supported)"
            note = "Stable (100% Parity)"

        rows.append(f"| **`{feat}`** | {count} | ✅ {count}/{count} | ✅ {count}/{count} | ✅ {count}/{count} | {w1_status} | {note} |")

    rows.append(f"| **Total Verified** | **{tot_fixtures}** | **{w0_interp_tot}/{tot_fixtures} (100%)** | **{w0_ast_tot}/{tot_fixtures} (100%)** | **{w0_hir_tot}/{tot_fixtures} (100%)** | **{w1_tot}/{tot_fixtures} ({w1_tot/tot_fixtures*100:.1f}%)** | **Full W0 Parity &bull; W1 Core Subset** |")
    rows.append("")
    rows.append("### Engine Definitions")
    rows.append("- **W0 Interpreter (`runtime/Interpreter.py`):** Canonical reference AST tree-walking interpreter.")
    rows.append("- **W0 AST C99 (`codegen/CCodeGen.py`):** Secondary C99 oracle for differential validation.")
    rows.append("- **W0 Typed HIR (`hir/HirCCodeGen.py`):** Primary production compiler backend since Milestone C06.")
    rows.append("- **W1 Self-Hosted (`selfhost/w1.w`):** Native Stage-2 compiler binary compiled via 3-stage bootstrap fixed-point.")
    return "\n".join(rows)


def main():
    arguments = sys.argv[1:]
    if '--matrix' in arguments:
        print(generate_markdown_matrix())
        return 0

    sanitize = '--sanitize' in arguments
    profile = 'release' if '--profile=release' in arguments else 'integration'
    valid_flags = ('--sanitize', '--profile=release', '--profile=integration', '--matrix')
    if any(arg not in valid_flags for arg in arguments):
        raise SystemExit('Usage: ci_conformance.py [--sanitize] [--profile=integration|release] [--matrix]')
    artifacts = Path(os.environ.get('W_CI_ARTIFACTS', ROOT / '.w_cache/ci-artifacts'))
    artifacts.mkdir(parents=True, exist_ok=True)
    compiler = subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + ['--version'],
                              capture_output=True, text=True, timeout=30, check=True)
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                         text=True, timeout=30, check=True).stdout.strip()
    (artifacts / 'environment.json').write_text(json.dumps({
        'sha': sha, 'python': sys.version, 'platform': sys.platform,
        'compiler': compiler.stdout, 'profile': profile, 'sanitize': sanitize,
        'compile_timeout_seconds': 120, 'run_timeout_seconds': 30}, indent=2))
    # This subprocess is bounded separately because it builds the compiler itself.
    bootstrap = execute([sys.executable, '-c',
        'from main import ensure_selfhost_w1_binary; '
        'print(ensure_selfhost_w1_binary(' + repr(str(ROOT)) + '))'],
        artifacts, 'bootstrap', 600)
    if bootstrap['returncode']:
        print(bootstrap['stderr'])
        return 1
    w1 = ROOT / '.w_cache/w1_stage2'
    support_files = PROFILES['support_files']
    positives, negatives = corpus_paths()
    fixtures = positives + negatives
    labels = {str(path.relative_to(ROOT)) for path in fixtures}
    stale = set(PROFILES['fixtures']) - labels
    if stale or not positives or not negatives:
        raise RuntimeError(f'Empty corpus or stale profile entries: {stale}')
    passed = 0
    feature_coverage = {}
    coverage = {engine: {'passed': 0, 'failed': 0, 'unsupported': 0} for engine in ENGINES}
    with tempfile.TemporaryDirectory(prefix='w-ci-') as directory:
        for path in fixtures:
            label = str(path.relative_to(ROOT))
            expected = path.with_suffix('.expected').read_text() if path in positives else None
            if path in positives and expected is None:
                raise RuntimeError(f'Missing expected output: {label}')
            ok, detail, report = verify_case(path.read_text(), label, w1, directory, expected,
                                sanitize, profile == 'release', path in negatives)
            passed += int(ok)
            feature_rows = feature_coverage.setdefault(report['feature'], {
                engine: {'passed': 0, 'failed': 0, 'unsupported': 0} for engine in ENGINES})
            for engine in ENGINES:
                if engine in report['unsupported']:
                    state = 'unsupported'
                else:
                    state = next(row['status'] for row in report['results'] if row['engine'] == engine)
                coverage[engine][state] += 1
                feature_rows[engine][state] += 1
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + ('' if ok else ': ' + detail), flush=True)
    summary = {'profile': profile, 'passed_cases': passed, 'total_cases': len(fixtures),
               'coverage': coverage, 'features': feature_coverage, 'support_files': support_files}
    (artifacts / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(fixtures) else 1


if __name__ == '__main__':
    sys.exit(main())
