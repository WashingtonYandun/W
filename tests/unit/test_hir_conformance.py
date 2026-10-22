import os
import sys
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from checker.TypeInterner import TYPE_ERROR
from hir.HirBuilder import HirBuilder
from hir.HirNodes import HirModule, HirExpr, HirStmt, HirBlock, HirFnDecl


def verify_expr_types(expr: HirExpr, file_name: str) -> None:
    assert hasattr(expr, "type_id"), f"Node {type(expr).__name__} in {file_name} missing type_id"
    # Recursively check sub-expressions if any
    for attr, val in expr.__dict__.items():
        if isinstance(val, HirExpr):
            verify_expr_types(val, file_name)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, HirExpr):
                    verify_expr_types(item, file_name)
                elif isinstance(item, tuple):
                    for sub in item:
                        if isinstance(sub, HirExpr):
                            verify_expr_types(sub, file_name)


def test_hir_suite() -> None:
    print("==================================================")
    print("Wysna Typed HIR Conformance Suite (SPEC v0.1)")
    print("==================================================")

    test_dirs = ["tests/runtime", "examples"]
    passed = 0
    total = 0
    failures = []

    for d in test_dirs:
        if not os.path.exists(d):
            continue
        files = sorted([f for f in os.listdir(d) if f.endswith(".wysna")])
        for f in files:
            total += 1
            path = os.path.join(d, f)
            with open(path, "r", encoding="utf-8") as stream:
                code = stream.read()

            try:
                ast = Parser(file=path).parse(code)
                checker = TypeChecker(file=path)
                checker.check(ast)

                builder = HirBuilder(checker.interner, file_path=path)
                hir_mod = builder.lower(ast)
                assert isinstance(hir_mod, HirModule), f"Expected HirModule, got {type(hir_mod)}"

                # Verify expressions in functions
                for fn in hir_mod.functions:
                    for stmt in fn.body.statements:
                        for attr, val in stmt.__dict__.items():
                            if isinstance(val, HirExpr):
                                verify_expr_types(val, f)

                # Verify top-level statements
                for stmt in hir_mod.top_level_stmts:
                    for attr, val in stmt.__dict__.items():
                        if isinstance(val, HirExpr):
                            verify_expr_types(val, f)

                print(f"  [PASS] {d}/{f}")
                passed += 1
            except Exception as e:
                print(f"  [FAIL] {d}/{f}: {e}")
                failures.append((f"{d}/{f}", str(e)))

    print("==================================================")
    print(f"Typed HIR Lowering: {passed}/{total}")
    print(f"FAILED:             {len(failures)}")
    print("==================================================")

    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("ALL TYPED HIR CONFORMANCE TESTS PASSED.")


if __name__ == "__main__":
    test_hir_suite()
