import os
import sys
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from error.Error import TypeError

def test_types_suite():
    valid_dir = "tests/types/valid"
    invalid_dir = "tests/types/invalid"

    valid_files = sorted([f for f in os.listdir(valid_dir) if f.endswith(".w")])
    invalid_files = sorted([f for f in os.listdir(invalid_dir) if f.endswith(".w")])

    valid_passed = 0
    invalid_passed = 0
    failures = []

    print("==================================================")
    print("W Language Type Checker Conformance Suite (SPEC v0.1)")
    print("==================================================")

    print(f"\n--- Types Valid ({len(valid_files)} tests) ---")
    for f in valid_files:
        path = os.path.join(valid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            parser = Parser(file=f)
            ast = parser.parse(code)
            checker = TypeChecker(file=f)
            checker.check(ast)

            print(f"  [PASS] {f}")
            valid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: {e}")
            failures.append((f, str(e)))

    print(f"\n--- Types Invalid ({len(invalid_files)} tests) ---")
    for f in invalid_files:
        path = os.path.join(invalid_dir, f)
        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        try:
            parser = Parser(file=f)
            ast = parser.parse(code)
            checker = TypeChecker(file=f)
            checker.check(ast)

            print(f"  [FAIL] {f}: Expected TypeError, but typechecking passed successfully")
            failures.append((f, "Expected TypeError but succeeded"))
        except TypeError as err:
            assert err.code.startswith("W") or err.code.startswith("T"), f"Type error code should start with 'W' or 'T', got {err.code}"
            assert err.line >= 1 and err.col >= 1, f"Invalid position line={err.line}, col={err.col}"
            print(f"  [PASS] {f}: Caught {err.code} at line {err.line}:{err.col} -> {err.message}")
            invalid_passed += 1
        except Exception as e:
            print(f"  [FAIL] {f}: Unexpected exception type {type(e).__name__}: {e}")
            failures.append((f, f"Wrong exception: {e}"))

    print("\n==================================================")
    print(f"Types valid:   {valid_passed}/{len(valid_files)}")
    print(f"Types invalid: {invalid_passed}/{len(invalid_files)}")
    print(f"FAILED:        {len(failures)}")
    print("==================================================")

    if failures:
        sys.exit(1)
    else:
        print("ALL TYPE CHECKER CONFORMANCE TESTS PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    test_types_suite()
