"""
test_hir_codegen_conformance.py - Conformance suite for Typed HIR -> C99 CodeGen.

Verifies that all runtime conformance tests lower to Typed HIR,
generate C99 via HirCCodeGen, compile natively with cc -std=c99 -O2,
and match their canonical .expected output with 100% fidelity.
"""

import os
import subprocess
import sys
import tempfile
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen


def run_hir_codegen_suite() -> bool:
    print("==================================================")
    print("W Language Typed HIR -> C99 Backend Conformance")
    print("==================================================")

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    runtime_dir = os.path.join(repo_root, "tests", "runtime")
    files = sorted([f for f in os.listdir(runtime_dir) if f.endswith(".w")])

    passed = 0
    total = 0
    failures = []

    for f in files:
        w_path = os.path.join(runtime_dir, f)
        expected_path = os.path.join(runtime_dir, f.replace(".w", ".expected"))
        if not os.path.exists(expected_path):
            continue

        total += 1
        with open(w_path, "r", encoding="utf-8") as stream:
            code = stream.read()
        with open(expected_path, "r", encoding="utf-8") as stream:
            expected_out = stream.read()

        with tempfile.TemporaryDirectory() as tmpdir:
            c_path = os.path.join(tmpdir, "out.c")
            bin_path = os.path.join(tmpdir, "out.bin")

            try:
                ast = Parser(file=w_path).parse(code)
                checker = TypeChecker(file=w_path)
                checker.check(ast)

                builder = HirBuilder(checker.interner, file_path=w_path)
                hir_mod = builder.lower(ast)

                gen = HirCCodeGen(checker.interner, file_path=w_path)
                c_code = gen.generate(hir_mod)

                with open(c_path, "w", encoding="utf-8") as cf:
                    cf.write(c_code)

                # Compile with cc
                cc_res = subprocess.run(
                    [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", c_path, "-o", bin_path],
                    timeout=120, capture_output=True,
                    text=True
                )
                if cc_res.returncode != 0:
                    failures.append((f, f"C compilation failed:\n{cc_res.stderr}"))
                    print(f"  [FAIL] {f} (C compilation)")
                    continue

                # Execute
                exec_env = os.environ.copy()
                exec_env["W_MEM_CHECK"] = "1"
                run_res = subprocess.run([bin_path], timeout=30, capture_output=True, text=True, env=exec_env)

                if run_res.returncode != 0:
                    failures.append((f, f"Execution failed with code {run_res.returncode}:\n{run_res.stderr}"))
                    print(f"  [FAIL] {f} (Runtime error)")
                    continue

                if run_res.stdout != expected_out:
                    failures.append((f, f"Output mismatch:\nGot:\n{run_res.stdout}\nExpected:\n{expected_out}"))
                    print(f"  [FAIL] {f} (Output mismatch)")
                    continue

                passed += 1
                print(f"  [PASS] {f}")

            except Exception as e:
                failures.append((f, str(e)))
                print(f"  [FAIL] {f} ({e})")

    print(f"\nHIR -> C99 Conformance: {passed}/{total} passed.")
    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"--- {name} ---\n{err}\n")
        return False
    return True


if __name__ == "__main__":
    if not run_hir_codegen_suite():
        sys.exit(1)
    sys.exit(0)
