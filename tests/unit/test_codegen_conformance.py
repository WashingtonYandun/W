import glob
import os
import subprocess
import sys
import tempfile
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from codegen.CCodeGen import CCodeGen


def run_codegen_tests() -> bool:
    w_files = sorted(glob.glob("tests/runtime/*.wysna"))
    passed = 0
    failed = 0
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("==========================================")
    print("W v0.1 Native C99 Backend Conformance Suite")
    print("==========================================")

    with tempfile.TemporaryDirectory() as tmpdir:
        for w_file in w_files:
            exp_file = w_file[:-6] + ".expected"
            if not os.path.exists(exp_file):
                continue

            with open(w_file, "r", encoding="utf-8") as f:
                src = f.read()
            with open(exp_file, "r", encoding="utf-8") as f:
                expected = f.read()

            try:
                ast = Parser(file=w_file).parse(src)
                TypeChecker(file=w_file).check(ast)
                c_code = CCodeGen(file=w_file).generate(ast)

                base = os.path.basename(w_file)[:-6]
                c_path = os.path.join(tmpdir, f"{base}.c")
                bin_path = os.path.join(tmpdir, base)

                with open(c_path, "w", encoding="utf-8") as f:
                    f.write(c_code)

                comp = subprocess.run(
                    ["cc", "-std=c99", f"-I{repo_root}", c_path, "-o", bin_path],
                    capture_output=True,
                    text=True
                )
                if comp.returncode != 0:
                    print(f"[FAIL] {os.path.basename(w_file)} (C compile error):\n{comp.stderr}")
                    failed += 1
                    continue

                run_res = subprocess.run([bin_path], capture_output=True, text=True)
                if run_res.stdout == expected:
                    print(f"[PASS] C99 {os.path.basename(w_file)}")
                    passed += 1
                else:
                    print(f"[FAIL] C99 {os.path.basename(w_file)} output mismatch")
                    print(f"  Expected: {repr(expected)}")
                    print(f"  Actual:   {repr(run_res.stdout)}")
                    failed += 1
            except Exception as e:
                print(f"[FAIL] C99 {os.path.basename(w_file)}: {e}")
                failed += 1

    print("------------------------------------------")
    print(f"C99 Backend Summary: {passed} passed, {failed} failed")
    print("==========================================")
    return failed == 0


if __name__ == "__main__":
    ok = run_codegen_tests()
    sys.exit(0 if ok else 1)
