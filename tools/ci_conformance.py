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
from tests.engine_harness import ENGINES, PROFILES, unsupported_reason, verify


def main():
    arguments = sys.argv[1:]
    sanitize = '--sanitize' in arguments
    profile = 'release' if '--profile=release' in arguments else 'integration'
    if any(arg not in ('--sanitize', '--profile=release', '--profile=integration') for arg in arguments):
        raise SystemExit('Usage: ci_conformance.py [--sanitize] [--profile=integration|release]')
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
    bootstrap = subprocess.run([sys.executable, '-c',
        'from main import ensure_selfhost_w1_binary; '
        'print(ensure_selfhost_w1_binary(' + repr(str(ROOT)) + '))'],
        cwd=ROOT, capture_output=True, text=True, timeout=600)
    (artifacts / 'bootstrap.txt').write_text(bootstrap.stdout + bootstrap.stderr)
    if bootstrap.returncode:
        print(bootstrap.stderr)
        return 1
    w1 = ROOT / '.w_cache/w1_stage2'
    positives = sorted((ROOT / 'tests/runtime').glob('*.w')) + sorted((ROOT / 'examples').glob('*.w'))
    support_files = PROFILES['support_files']
    positives = [path for path in positives if str(path.relative_to(ROOT)) not in support_files]
    negatives = sorted((ROOT / 'tests').glob('*/invalid/*.w')) + sorted((ROOT / 'tests/errors').glob('invalid_*.w'))
    fixtures = positives + negatives
    labels = {str(path.relative_to(ROOT)) for path in fixtures}
    stale = set(PROFILES['fixtures']) - labels
    if stale or not positives or not negatives:
        raise RuntimeError(f'Empty corpus or stale profile entries: {stale}')
    passed = 0
    coverage = {engine: {'passed': 0, 'failed': 0, 'unsupported': 0} for engine in ENGINES}
    with tempfile.TemporaryDirectory(prefix='w-ci-') as directory:
        for path in fixtures:
            label = str(path.relative_to(ROOT))
            expected = path.with_suffix('.expected').read_text() if path in positives else None
            if path in positives and expected is None:
                raise RuntimeError(f'Missing expected output: {label}')
            ok, detail = verify(path.read_text(), label, w1, directory, expected,
                                sanitize, profile == 'release', path in negatives)
            passed += int(ok)
            for engine in ENGINES:
                state = 'unsupported' if unsupported_reason(label, engine) else ('passed' if ok else 'failed')
                coverage[engine][state] += 1
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + ('' if ok else ': ' + detail), flush=True)
    summary = {'profile': profile, 'passed_cases': passed, 'total_cases': len(fixtures),
               'coverage': coverage, 'support_files': support_files}
    (artifacts / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(fixtures) else 1


if __name__ == '__main__':
    sys.exit(main())
