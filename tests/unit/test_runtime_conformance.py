import io
import os
import sys
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from error.Error import WError

def test_runtime_suite():
    runtime_dir = "tests/runtime"
    if not os.path.exists(runtime_dir):
        print(f"Directory {runtime_dir} not found.")
        sys.exit(1)

    w_files = sorted([f for f in os.listdir(runtime_dir) if f.endswith(".w")])
    passed = 0
    failures = []

    print("==================================================")
    print("W Language Runtime Conformance Suite (SPEC v0.1)")
    print("==================================================")
    print(f"\n--- Running Runtime Tests ({len(w_files)} files) ---")

    for f in w_files:
        path = os.path.join(runtime_dir, f)
        expected_path = os.path.join(runtime_dir, f[:-2] + ".expected")

        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        buf = io.StringIO()
        try:
            # 1. Parse
            ast = Parser(file=f).parse(code)

            # 2. Type Check
            TypeChecker(file=f).check(ast)

            # 3. Interpret
            interp = Interpreter(stdout=buf, file=path)
            interp.interpret(ast)

            actual_output = buf.getvalue().strip()

            # 4. Verify against expected output if present
            if os.path.exists(expected_path):
                with open(expected_path, "r", encoding="utf-8") as exp_stream:
                    expected_output = exp_stream.read().strip()

                if actual_output != expected_output:
                    print(f"  [FAIL] {f}: Output mismatch")
                    print(f"    Expected:\n{expected_output}")
                    print(f"    Actual:\n{actual_output}")
                    failures.append((f, "Output mismatch"))
                    continue

            print(f"  [PASS] {f}")
            passed += 1

        except WError as w_err:
            print(f"  [FAIL] {f}: Diagnostic error {w_err}")
            failures.append((f, str(w_err)))
        except Exception as e:
            print(f"  [FAIL] {f}: Unexpected exception {e}")
            failures.append((f, str(e)))

    # Clean any temporary files generated during I/O tests
    temp_file = os.path.join(runtime_dir, "temp_file.txt")
    if os.path.exists(temp_file):
        try:
            os.remove(temp_file)
        except OSError:
            pass

    print("\n==================================================")
    print(f"Runtime tests passed: {passed}/{len(w_files)}")
    print(f"FAILED:                {len(failures)}")
    print("==================================================")

    if failures:
        sys.exit(1)
    else:
        print("ALL RUNTIME CONFORMANCE TESTS PASSED (100%).")
        sys.exit(0)

if __name__ == "__main__":
    test_runtime_suite()
