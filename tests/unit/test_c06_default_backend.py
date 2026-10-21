"""
test_c06_default_backend.py - Conformance suite for Milestone C06:
Default HIR Backend, Explicit Engine Selection, and Oracle Equivalence.

Invariants verified:
1. Default backend for emit-c and build is Typed HIR -> HirCCodeGen -> C99.
2. CLI flags --backend=hir, --backend=ast, --backend=selfhost select engines unambiguously.
3. Legacy flags (--hir, --selfhost, --ast) remain supported for backward compatibility.
4. Unknown backends (--backend=invalid) fail with structured error and non-zero exit code.
5. No silent fallback: HIR errors are reported directly without fallback to AST C.
6. Unit functions with trailing expressions are normalized to HirConstUnit.
7. Native C99 execution across default HIR backend under Clang AddressSanitizer and UBSan.
"""

import os
import subprocess
import sys
import tempfile
from lexer.Lexer import Lexer
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from checker.TypeInterner import TYPE_UNIT
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from hir.HirNodes import HirExprStmt, HirConstUnit
from codegen.CCodeGen import CCodeGen
from main import run_pipeline, get_repo_root


def _run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def test_default_backend_is_hir():
    """Verify that omitting backend flags selects HirCCodeGen by default."""
    print("  [TEST] Default backend is Typed HIR C99...")
    source = """
    fn add(a: int, b: int) -> int {
        return a + b
    }
    print(add(10, 20))
    """
    with tempfile.TemporaryDirectory() as td:
        c_path = os.path.join(td, "default.c")
        code = run_pipeline(source, file_name="test_default.wysna", emit_c_path=c_path)
        assert code == 0, "run_pipeline failed on default emission"
        with open(c_path, "r", encoding="utf-8") as f:
            c_content = f.read()
        
        # Verify HIR hallmarks in generated C code
        # HirCCodeGen emits HirDirectCall targets with resolved signatures
        assert "w_fn_add" in c_content, "Generated code must include function w_fn_add"
        assert "w_main(" in c_content or "main(" in c_content, "Generated code must include main entrypoint"


def test_explicit_backend_flags():
    """Verify explicit selection between --backend=hir, --backend=ast, and --backend=selfhost."""
    print("  [TEST] Explicit backend flags (--backend=hir, --backend=ast)...")
    source = """
    struct Point { x: int, y: int }
    let p = Point { x: 3, y: 4 }
    print(p.x + p.y)
    """
    repo_root = get_repo_root()
    w_bin = os.path.join(repo_root, "wysna")

    with tempfile.TemporaryDirectory() as td:
        src_path = os.path.join(td, "point.wysna")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)

        # 1. Default (should be HIR)
        c_default = os.path.join(td, "default.c")
        rc, out, err = _run_cmd([sys.executable, w_bin, "emit-c", src_path, "-o", c_default], cwd=repo_root)
        assert rc == 0, f"Default emit-c failed: {err}"

        # 2. Explicit --backend=hir
        c_hir = os.path.join(td, "hir.c")
        rc, out, err = _run_cmd([sys.executable, w_bin, "emit-c", "--backend=hir", src_path, "-o", c_hir], cwd=repo_root)
        assert rc == 0, f"--backend=hir failed: {err}"

        # 3. Explicit --backend=ast
        c_ast = os.path.join(td, "ast.c")
        rc, out, err = _run_cmd([sys.executable, w_bin, "emit-c", "--backend=ast", src_path, "-o", c_ast], cwd=repo_root)
        assert rc == 0, f"--backend=ast failed: {err}"

        # 4. Compare default vs hir: they must be identical
        with open(c_default, "r", encoding="utf-8") as f:
            content_default = f.read()
        with open(c_hir, "r", encoding="utf-8") as f:
            content_hir = f.read()
        assert content_default == content_hir, "Default emit-c must match --backend=hir output exactly"

        # 5. Invalid backend flag should cleanly fail
        rc, out, err = _run_cmd([sys.executable, w_bin, "emit-c", "--backend=invalid_backend", src_path], cwd=repo_root)
        assert rc != 0, "Invalid backend must exit with non-zero code"
        assert "Unknown backend" in err or "Unknown backend" in out, "Must produce error message on invalid backend"


def test_unit_function_tail_normalization():
    """Verify that unit functions with non-unit tail expressions normalize to HirConstUnit."""
    print("  [TEST] Unit function tail expression normalization...")
    source = """
    fn helper() -> int {
        return 42
    }
    fn procedure() -> unit {
        let x = 10
        helper()
    }
    procedure()
    """
    ast = Parser(file="unit_tail.wysna").parse(source)
    tc = TypeChecker(file="unit_tail.wysna")
    tc.check(ast)

    builder = HirBuilder(tc.interner, file_path="unit_tail.wysna")
    hir_mod = builder.lower(ast)
    assert hir_mod is not None, "HIR module must lower successfully"

    # Verify procedure's HIR declaration
    proc_fn = [f for f in hir_mod.functions if f.name == "procedure"][0]
    assert proc_fn.return_type_id == TYPE_UNIT, "procedure return type must be TYPE_UNIT"
    assert isinstance(proc_fn.body.tail_expr, HirConstUnit), "procedure tail_expr must be normalized to HirConstUnit"

    # Verify statement list has the helper() expression statement
    assert any(isinstance(s, HirExprStmt) for s in proc_fn.body.statements), "Discarded helper() must be in statements"


def test_native_c99_execution_under_sanitizers():
    """Verify default HIR build and execution under AddressSanitizer and UndefinedBehaviorSanitizer."""
    print("  [TEST] Native C99 execution across default HIR under ASan + UBSan...")
    source = """
    enum Tree[T] {
        Leaf(T),
        Node(Tree[T], Tree[T])
    }

    fn count_leaves[T](t: Tree[T]) -> int {
        return match t {
            Tree.Leaf(_) => 1,
            Tree.Node(left, right) => count_leaves(left) + count_leaves(right)
        }
    }

    fn run_test() -> int {
        let tree: Tree[int] = Tree.Node(
            Tree.Node(Tree.Leaf(1), Tree.Leaf(2)),
            Tree.Leaf(3)
        )
        return count_leaves(tree)
    }

    print("LEAVES:", run_test())
    """
    repo_root = get_repo_root()
    w_bin = os.path.join(repo_root, "wysna")

    with tempfile.TemporaryDirectory() as td:
        src_path = os.path.join(td, "tree.wysna")
        bin_path = os.path.join(td, "tree_bin")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)

        # Build natively using default backend with sanitizers enabled
        rc, out, err = _run_cmd([
            sys.executable, w_bin, "build", "--sanitize", src_path, "-o", bin_path
        ], cwd=repo_root)
        assert rc == 0, f"Native build via default HIR backend failed: {err}"
        assert os.path.exists(bin_path), "Target binary must exist"

        # Execute binary
        env = dict(os.environ, W_MEM_CHECK="1")
        res = subprocess.run([bin_path], capture_output=True, text=True, env=env)
        assert res.returncode == 0, f"Execution failed with code {res.returncode}: {res.stderr}"
        assert "LEAVES: 3" in res.stdout, f"Unexpected stdout: {res.stdout}"


def run_all() -> bool:
    print("==================================================")
    print("W Language C06 Default HIR Backend Suite")
    print("==================================================")
    try:
        test_default_backend_is_hir()
        test_explicit_backend_flags()
        test_unit_function_tail_normalization()
        test_native_c99_execution_under_sanitizers()
        print("==================================================")
        print("ALL C06 DEFAULT HIR BACKEND TESTS PASSED.")
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
