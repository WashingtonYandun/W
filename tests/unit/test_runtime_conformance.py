import io
import os
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from error.Error import WError
from tests.engine_harness import panic_expectation

def test_runtime_suite():
    runtime_dir = "tests/runtime"
    if not os.path.exists(runtime_dir):
        raise AssertionError(f"Directory {runtime_dir} not found.")

    w_files = sorted([f for f in os.listdir(runtime_dir) if f.endswith(".wysna")])
    passed = 0
    failures = []

    print("==================================================")
    print("W Language Runtime Conformance Suite (SPEC v0.1)")
    print("==================================================")
    print(f"\n--- Running Runtime Tests ({len(w_files)} files) ---")

    for f in w_files:
        path = os.path.join(runtime_dir, f)
        expected_path = os.path.join(runtime_dir, f[:-6] + ".expected")

        with open(path, "r", encoding="utf-8") as stream:
            code = stream.read()

        buf = io.StringIO()
        expected_text = ""
        if os.path.exists(expected_path):
            with open(expected_path, "r", encoding="utf-8") as exp_stream:
                expected_text = exp_stream.read()
        panic_code = panic_expectation(expected_text)
        try:
            # 1. Parse
            ast = Parser(file=f).parse(code)

            # 2. Type Check
            TypeChecker(file=f).check(ast)

            # 3. Interpret
            interp = Interpreter(stdout=buf, file=path)
            interp.interpret(ast)

            if panic_code is not None:
                failures.append((f, f"Expected runtime panic {panic_code}, but interpretation succeeded"))
                print(f"  [FAIL] {f}: Expected runtime panic {panic_code}, but interpretation succeeded")
                continue

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
            if panic_code is not None and w_err.code == panic_code:
                print(f"  [PASS] {f}: Caught expected {w_err.code}")
                passed += 1
            else:
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

    assert not failures, f"Runtime conformance failures: {failures}"
    print("ALL RUNTIME CONFORMANCE TESTS PASSED.")

if __name__ == "__main__":
    test_runtime_suite()
