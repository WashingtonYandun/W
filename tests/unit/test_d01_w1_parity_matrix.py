"""
test_d01_w1_parity_matrix.py - Conformance suite for Milestone D01:
Public Engine Feature Parity Matrix, Boundary Transparency, and Standalone W1 Validation.

Invariants verified:
1. Every fixture in the corpus is classified in tests/engine_profiles.json without stale entries.
2. Every unsupported engine feature has an explicit, non-empty tracking reason pointing to its milestone.
3. Standalone W1 binary executes directly on core fixtures without W0 pre-filtering.
4. Standalone W1 binary rejects unsupported generic features with the documented semantic diagnostic.
5. ci_conformance.py --matrix generates a valid Markdown parity matrix matching current counts.
6. docs/ENGINE_PARITY_MATRIX.md matches the actual engine status reported by the harness.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def test_fixture_accounting_and_staleness():
    """Verify that every fixture in the corpus is tracked and no stale entries exist."""
    print("  [TEST] Fixture accounting and profile freshness...")
    profiles_path = ROOT / "tests/engine_profiles.json"
    assert profiles_path.exists(), "engine_profiles.json must exist"
    profiles = json.loads(profiles_path.read_text())

    from tests.engine_harness import corpus_paths
    positives, negatives = corpus_paths()
    fixtures = positives + negatives

    labels = {str(p.relative_to(ROOT)) for p in fixtures}
    stale = set(profiles.get("fixtures", {}).keys()) - labels
    assert not stale, f"Found stale fixture entries in engine_profiles.json: {stale}"

    # Verify every fixture is mapped to a declared feature
    declared_features = set(profiles.get("features", {}).keys())
    for label in labels:
        feat = profiles.get("fixtures", {}).get(label, "core")
        assert feat in declared_features, f"Fixture '{label}' mapped to unknown feature '{feat}'"


def test_unsupported_reasons_and_milestones():
    """Verify that all unsupported engine entries have clear, non-empty tracking reasons."""
    print("  [TEST] Explicit tracking reasons for unsupported engine features...")
    profiles = json.loads((ROOT / "tests/engine_profiles.json").read_text())
    features = profiles.get("features", {})

    # Core must be supported across all engines
    core = features.get("core", {})
    assert not core, f"Core feature must have no engine limitations, found: {core}"

    roadmap_text = (ROOT / "docs/ROADMAP.md").read_text()
    roadmap_milestones = set(re.findall(r"\b[A-Z]\d{2}\b", roadmap_text))

    # Every limitation must point to a milestone that exists in the active roadmap.
    for feat_name, limitations in features.items():
        for engine, reason in limitations.items():
            assert reason, f"Feature '{feat_name}' engine '{engine}' has empty unsupported reason"
            reason_milestones = set(re.findall(r"\b[A-Z]\d{2}\b", reason))
            assert roadmap_milestones.intersection(reason_milestones), (
                f"Feature '{feat_name}' engine '{engine}' reason must reference roadmap milestone: {reason}"
            )


def test_standalone_w1_execution_contracts():
    """Verify standalone W1 core success and explicit generic rejection."""
    print("  [TEST] Standalone W1 execution contracts (core success vs generic rejection)...")
    from main import ensure_selfhost_w1_binary
    w1_bin = ensure_selfhost_w1_binary(str(ROOT))
    assert os.path.exists(w1_bin), f"W1 binary must exist at {w1_bin}"

    with tempfile.TemporaryDirectory() as td:
        # 1. Core fixture: must compile cleanly standalone
        core_c = os.path.join(td, "core_out.c")
        core_src = str(ROOT / "tests/runtime/arithmetic.w")
        rc, out, err = _run_cmd([w1_bin, core_src, core_c], cwd=str(ROOT))
        assert rc == 0, f"Standalone W1 failed on core fixture '{core_src}': {err}"
        assert os.path.exists(core_c), "W1 must emit C file for core fixture"

        # 2. Generic fixture: must fail directly without crashing or hanging
        gen_c = os.path.join(td, "gen_out.c")
        gen_src = str(ROOT / "tests/runtime/generic_function.w")
        rc_gen, out_gen, err_gen = _run_cmd([w1_bin, gen_src, gen_c], cwd=str(ROOT))
        assert rc_gen != 0, f"Standalone W1 should have rejected unsupported generic fixture '{gen_src}'"
        assert "[W2013]" in err_gen, (
            f"Expected W1 generic rejection diagnostic, got: {err_gen or out_gen}"
        )
        assert "generic specialization is not implemented" in err_gen, (
            f"Expected the documented generic limitation diagnostic, got: {err_gen or out_gen}"
        )


def test_ci_matrix_generation_tooling():
    """Verify that ci_conformance.py --matrix emits expected table accurately."""
    print("  [TEST] ci_conformance.py --matrix generator...")
    rc, out, err = _run_cmd([sys.executable, str(ROOT / "tools/ci_conformance.py"), "--matrix"], cwd=str(ROOT))
    assert rc == 0, f"--matrix command failed: {err}"
    assert "# W Language Engine Feature Parity Matrix" in out, "Output must contain matrix header"
    assert "| **`core`** |" in out, "Output must contain core row"
    assert "| **`generics`** |" in out, "Output must contain generics row"
    assert "| **Total Verified** |" in out, "Output must contain total row"
    # The matrix must report measured per-engine numbers, not a restatement of the
    # declaration file. Previously this test asserted the literal strings "91/91" and
    # "0/15", which passed even when no compiler was ever executed.
    import re as _re
    from tests.engine_harness import corpus_paths
    assert "measurements, not a" in out, "Matrix must state that counts are measured"
    totals = _re.search(r"\| \*\*Total Verified\*\* \| \*\*(\d+)\*\* \|(.+)\|", out)
    assert totals, "Matrix must contain a parseable total row"
    corpus = int(totals.group(1))
    assert corpus == len(corpus_paths()[0]) + len(corpus_paths()[1]), \
        f"Matrix corpus size {corpus} does not match the real corpus"
    header = out.splitlines()[2]
    for column in ("W0 Interpreter", "W0 AST C99", "W0 Typed HIR (Default)", "W1 Self-Hosted C99"):
        assert column in header, f"Matrix header is missing the '{column}' column"
    if "\u2014" in totals.group(2):
        # No verified run available in this workspace; that is reported, not faked.
        assert "no verified run" in out, "Missing run must be reported explicitly"


def test_documentation_consistency():
    """Keep published engine and expansion limits aligned with the measured corpus."""
    print("  [TEST] Documentation consistency in docs/ENGINE_PARITY_MATRIX.md...")
    doc_path = ROOT / "docs/ENGINE_PARITY_MATRIX.md"
    assert doc_path.exists(), "docs/ENGINE_PARITY_MATRIX.md must exist"
    content = doc_path.read_text()

    # The doc is a report, so the check is that it stays internally consistent rather
    # than that it repeats a number copied into this test.
    from tests.engine_harness import corpus_paths
    import re as _re
    corpus_size = len(corpus_paths()[0]) + len(corpus_paths()[1])
    total_row = _re.search(r"\| \*\*Total Verified\*\* \| \*\*(\d+)\*\*", content)
    assert total_row, "Doc must contain a generated Total Verified row"
    assert int(total_row.group(1)) == corpus_size, (
        f"Doc reports a corpus of {total_row.group(1)} but the real corpus is {corpus_size}; "
        f"rerun: python3 tools/ci_conformance.py --matrix")
    assert "Milestone F01" in content, "Doc must reference the active F01 remediation milestone"
    roadmap = (ROOT / "docs/ROADMAP.md").read_text()
    assert "F01" in roadmap and "114" in roadmap, "Roadmap must define measurable F01 acceptance"
    assert "Bootstrap Fixed-Point vs. Core Corpus Parity" in content, (
        "Doc must distinguish bootstrap fixed-point from core-corpus parity"
    )

    expansion = (ROOT / "docs/EXPANSION.md").read_text()
    assert f"{corpus_size} fixtures" in expansion, (
        "Expansion docs must quote the current core corpus size, not a stale count"
    )
    assert "107 fixtures" not in expansion, "Stale expansion corpus count must be removed"

    limits = (ROOT / "docs/KNOWN_LIMITS.md").read_text()
    assert "Lambda and callable syntax" not in limits, (
        "W1 supports first-class calls and closures in the tested expansion cases"
    )


def run_all() -> bool:
    print("==================================================")
    print("W Language D01 W1 Parity Matrix Suite")
    print("==================================================")
    try:
        test_fixture_accounting_and_staleness()
        test_unsupported_reasons_and_milestones()
        test_standalone_w1_execution_contracts()
        test_ci_matrix_generation_tooling()
        test_documentation_consistency()
        print("==================================================")
        print("ALL D01 W1 PARITY MATRIX TESTS PASSED.")
        print("==================================================")
        return True
    except AssertionError as e:
        print(f"[FAIL] Assertion error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
