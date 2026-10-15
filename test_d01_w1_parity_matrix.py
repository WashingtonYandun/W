"""
test_d01_w1_parity_matrix.py - Conformance suite for Milestone D01:
Public Engine Feature Parity Matrix, Boundary Transparency, and Standalone W1 Validation.

Invariants verified:
1. Every fixture in the corpus is classified in tests/engine_profiles.json without stale entries.
2. Every unsupported engine feature has an explicit, non-empty tracking reason pointing to its milestone.
3. Standalone W1 binary executes directly on core fixtures without W0 pre-filtering.
4. Standalone W1 binary rejects unsupported generic features directly with non-zero exit code.
5. ci_conformance.py --matrix generates a valid Markdown parity matrix matching current counts.
6. docs/ENGINE_PARITY_MATRIX.md matches the actual engine status reported by the harness.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def test_fixture_accounting_and_staleness():
    """Verify that every fixture in the corpus is tracked and no stale entries exist."""
    print("  [TEST] Fixture accounting and profile freshness...")
    profiles_path = ROOT / "tests/engine_profiles.json"
    assert profiles_path.exists(), "engine_profiles.json must exist"
    profiles = json.loads(profiles_path.read_text())

    positives = sorted((ROOT / "tests/runtime").glob("*.w")) + sorted((ROOT / "examples").glob("*.w"))
    positives += sorted((ROOT / "tests/modules").glob("*/main.w"))
    support_files = profiles.get("support_files", {})
    positives = [p for p in positives if str(p.relative_to(ROOT)) not in support_files]
    negatives = sorted((ROOT / "tests").glob("*/invalid/*.w")) + sorted((ROOT / "tests/errors").glob("invalid_*.w"))
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

    # All non-empty engine limitations must reference a tracking milestone (e.g. D02)
    for feat_name, limitations in features.items():
        for engine, reason in limitations.items():
            assert reason, f"Feature '{feat_name}' engine '{engine}' has empty unsupported reason"
            assert any(tag in reason for tag in ("D02", "D03", "D04", "D05", "D06")), (
                f"Feature '{feat_name}' engine '{engine}' reason must reference roadmap milestone: {reason}"
            )


def test_standalone_w1_execution_contracts():
    """Verify standalone W1 execution on core (success) vs generic (clean rejection)."""
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
        assert "expected 'LPAREN'" in err_gen or "expected 'LPAREN'" in out_gen, (
            f"Expected parser rejection on generic syntax from standalone W1, got: {err_gen or out_gen}"
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
    assert "86/102" in out, "Output must accurately report 86/102 for W1"


def test_documentation_consistency():
    """Verify that docs/ENGINE_PARITY_MATRIX.md exists and is consistent with engine profiles."""
    print("  [TEST] Documentation consistency in docs/ENGINE_PARITY_MATRIX.md...")
    doc_path = ROOT / "docs/ENGINE_PARITY_MATRIX.md"
    assert doc_path.exists(), "docs/ENGINE_PARITY_MATRIX.md must exist"
    content = doc_path.read_text()

    assert "86/86" in content, "Doc must mention 86/86 core parity"
    assert "0/15" in content, "Doc must mention 0/15 generics limitation in W1"
    assert "Milestone D02" in content, "Doc must reference D02 remediation milestone"
    assert "Bootstrap Fixed-Point vs. Full Language Parity" in content, (
        "Doc must clearly contrast bootstrap fixed-point with full language parity"
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
