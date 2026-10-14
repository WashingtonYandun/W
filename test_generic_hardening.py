"""
test_generic_hardening.py - Conformance tests for generic hardening and code bloat metrics.

Verifies:
1. Canonical GenericInstanceKey hash and equality semantics.
2. Monomorphization caching and deduplication telemetry.
3. Structural growth cycle detection (W2011).
4. Direct recursive struct cycle detection (W2011).
5. CLI --stats output format and telemetry fields.
"""

import json
import os
import subprocess
import sys
from checker.TypeChecker import TypeChecker, GenericInstanceKey
from parser.Parser import Parser
from error.Error import TypeError


def test_generic_instance_key():
    k1 = GenericInstanceKey("Box", (1, 2))
    k2 = GenericInstanceKey("Box", (1, 2))
    k3 = GenericInstanceKey("Box", (1, 3))
    k4 = GenericInstanceKey("Pair", (1, 2))

    assert k1 == k2, "Identical keys must compare equal"
    assert hash(k1) == hash(k2), "Identical keys must have equal hashes"
    assert k1 != k3, "Keys with different type IDs must not compare equal"
    assert k1 != k4, "Keys with different template names must not compare equal"

    d = {k1: "cached"}
    assert d.get(k2) == "cached", "Key lookup in dictionary must succeed via hash/eq"
    print("  [PASS] GenericInstanceKey hashing and equality")


def test_canonical_deduplication_telemetry():
    code = """
    struct Box[T] {
        val: T
    }

    fn get_val[T](b: Box[T]) -> T {
        return b.val
    }

    let b1 = Box(10)
    let b2 = Box(20)
    let v1 = get_val(b1)
    let v2 = get_val(b2)
    """
    ast = Parser(file="test_dedup.w").parse(code)
    checker = TypeChecker(file="test_dedup.w")
    checker.check(ast)

    telem = checker.telemetry
    assert telem.specialized_structs == 1, f"Expected 1 specialized struct, got {telem.specialized_structs}"
    assert telem.specialized_functions == 1, f"Expected 1 specialized fn, got {telem.specialized_functions}"
    assert telem.specialization_requests > 2, f"Expected >2 specialization requests, got {telem.specialization_requests}"
    assert telem.deduplicated_hits > 0, f"Expected >0 deduplicated hits, got {telem.deduplicated_hits}"
    print("  [PASS] Canonical deduplication telemetry")


def test_structural_growth_cycle_detection():
    code = """
    fn expand[T](x: T) {
        expand([x])
    }

    expand(10)
    """
    ast = Parser(file="test_growth.w").parse(code)
    checker = TypeChecker(file="test_growth.w")
    caught = False
    try:
        checker.check(ast)
    except TypeError as err:
        assert err.code == "W2011", f"Expected W2011, got {err.code}"
        assert "Structurally growing" in str(err), f"Expected structural growth message, got {err}"
        caught = True
    assert caught, "Expected TypeError W2011 for structural growth cycle"
    print("  [PASS] Structural growth cycle detection (W2011)")


def test_direct_struct_recursion_cycle_detection():
    code = """
    struct Node[T] {
        val: T,
        next: Node[T]
    }

    let n: Node[int] = Node(1, Node(2, 0))
    """
    ast = Parser(file="test_direct.w").parse(code)
    checker = TypeChecker(file="test_direct.w")
    caught = False
    try:
        checker.check(ast)
    except TypeError as err:
        assert err.code == "W2011", f"Expected W2011, got {err.code}"
        assert "Recursive generic struct cycle" in str(err), f"Expected recursive cycle message, got {err}"
        caught = True
    assert caught, "Expected TypeError W2011 for direct struct recursion"
    print("  [PASS] Direct struct recursion cycle detection (W2011)")


def test_cli_stats_output():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(repo_root, "main.py")
    test_w = os.path.join(repo_root, "tests", "runtime", "generic_tree_recursive.w")
    proc = subprocess.run(
        [sys.executable, main_py, test_w, "--stats"],
        capture_output=True,
        text=True,
        cwd=repo_root
    )
    assert proc.returncode == 0, f"CLI error: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data.get("status") == "ok", "Expected status ok in JSON stats"
    telemetry = data.get("telemetry", {})
    assert "monomorphization" in telemetry, "Expected monomorphization in telemetry"
    assert "codegen" in telemetry, "Expected codegen in telemetry"
    mono = telemetry["monomorphization"]
    assert mono["specialized_structs"] == 1, f"Expected 1 specialized struct, got {mono['specialized_structs']}"
    assert mono["specialized_enums"] == 1, f"Expected 1 specialized enum, got {mono['specialized_enums']}"
    codegen = telemetry["codegen"]
    assert codegen["generated_c_lines"] > 0, "Expected generated_c_lines > 0"
    print("  [PASS] CLI --stats JSON output and telemetry verification")


def run_generic_hardening_tests() -> bool:
    print("==================================================")
    print("Generic Hardening & Code Bloat Metrics Conformance")
    print("==================================================")
    try:
        test_generic_instance_key()
        test_canonical_deduplication_telemetry()
        test_structural_growth_cycle_detection()
        test_direct_struct_recursion_cycle_detection()
        test_cli_stats_output()
        return True
    except Exception as e:
        print(f"  [FAIL] Generic Hardening Test Failed: {e}")
        return False


if __name__ == "__main__":
    if not run_generic_hardening_tests():
        sys.exit(1)
    print("\n[OK] Generic Hardening Conformance: 100% PASS.")
    sys.exit(0)
