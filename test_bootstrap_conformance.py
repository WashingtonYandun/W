import glob
import hashlib
import os
import subprocess
import sys
import tempfile
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from codegen.CCodeGen import CCodeGen


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def run_bootstrap_test() -> bool:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    w1_src_path = os.path.join(repo_root, "selfhost", "w1.w")

    print("==================================================")
    print("W Language Self-Hosting Bootstrap Suite (SPEC 11)")
    print("==================================================")

    with open(w1_src_path, "r", encoding="utf-8") as f:
        src = f.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Stage 0 (W0 Python Compiler -> compiler0.c -> w1_stage1 binary)
        ast = Parser(file=w1_src_path).parse(src)
        TypeChecker(file=w1_src_path).check(ast)
        c0_code = CCodeGen(file=w1_src_path).generate(ast)

        compiler0_c = os.path.join(tmpdir, "compiler0.c")
        w1_stage1 = os.path.join(tmpdir, "w1_stage1")
        with open(compiler0_c, "w", encoding="utf-8") as f:
            f.write(c0_code)

        res1 = subprocess.run(
            ["cc", "-std=c99", "-O2", f"-I{repo_root}", compiler0_c, "-o", w1_stage1],
            capture_output=True,
            text=True
        )
        if res1.returncode != 0:
            print(f"[FAIL] Stage 0 -> Stage 1 C compilation failed:\n{res1.stderr}")
            return False
        print("  [PASS] Stage 0: W0 compiled selfhost/w1.w -> compiler0.c -> w1_stage1")

        # 2. Stage 1 (w1_stage1 native binary -> compiler1.c -> w1_stage2 binary)
        compiler1_c = os.path.join(tmpdir, "compiler1.c")
        w1_stage2 = os.path.join(tmpdir, "w1_stage2")
        run1 = subprocess.run([w1_stage1, w1_src_path, compiler1_c], capture_output=True, text=True)
        if run1.returncode != 0 or not os.path.exists(compiler1_c):
            print(f"[FAIL] Stage 1 execution failed:\n{run1.stderr}\n{run1.stdout}")
            return False

        res2 = subprocess.run(
            ["cc", "-std=c99", "-O2", f"-I{repo_root}", compiler1_c, "-o", w1_stage2],
            capture_output=True,
            text=True
        )
        if res2.returncode != 0:
            print(f"[FAIL] Stage 1 -> Stage 2 C compilation failed:\n{res2.stderr}")
            return False
        print("  [PASS] Stage 1: w1_stage1 compiled selfhost/w1.w -> compiler1.c -> w1_stage2")

        # 3. Stage 2 (w1_stage2 native binary -> compiler2.c)
        compiler2_c = os.path.join(tmpdir, "compiler2.c")
        run2 = subprocess.run([w1_stage2, w1_src_path, compiler2_c], capture_output=True, text=True)
        if run2.returncode != 0 or not os.path.exists(compiler2_c):
            print(f"[FAIL] Stage 2 execution failed:\n{run2.stderr}\n{run2.stdout}")
            return False
        print("  [PASS] Stage 2: w1_stage2 compiled selfhost/w1.w -> compiler2.c")

        # 4. Fixed-Point Hash Verification
        h0 = sha256_file(compiler0_c)
        h1 = sha256_file(compiler1_c)
        h2 = sha256_file(compiler2_c)

        print(f"  SHA256(compiler0.c) = {h0}")
        print(f"  SHA256(compiler1.c) = {h1}")
        print(f"  SHA256(compiler2.c) = {h2}")

        if h1 != h2 or h0 != h1:
            print("[FAIL] Fixed-Point verification failed: SHA256 mismatch across stages!")
            return False

        print("  [PASS] Fixed-Point verified: SHA256(compiler0.c) == SHA256(compiler1.c) == SHA256(compiler2.c)")

        # 5. Stage 2 Native Binary Compiles & Runs Full Runtime Suite
        w_files = sorted(glob.glob(os.path.join(repo_root, "tests", "runtime", "*.w")))
        w1_passed = 0
        w1_total = 0
        for w_file in w_files:
            exp_file = w_file[:-2] + ".expected"
            if not os.path.exists(exp_file):
                continue
            w1_total += 1
            with open(exp_file, "r", encoding="utf-8") as ef:
                expected = ef.read()
            base = os.path.basename(w_file)[:-2]
            out_c = os.path.join(tmpdir, f"w1_{base}.c")
            out_bin = os.path.join(tmpdir, f"w1_{base}")

            r_w1 = subprocess.run([w1_stage2, w_file, out_c], capture_output=True, text=True, cwd=repo_root)
            if r_w1.returncode != 0:
                print(f"  [FAIL W1] {base}.w compile failed: {r_w1.stderr}")
                return False
            r_cc = subprocess.run(["cc", "-std=c99", f"-I{repo_root}", out_c, "-o", out_bin], capture_output=True, text=True)
            if r_cc.returncode != 0:
                print(f"  [FAIL W1 CC] {base}.c failed: {r_cc.stderr}")
                return False
            r_run = subprocess.run([out_bin], capture_output=True, text=True, cwd=repo_root)
            if r_run.stdout != expected:
                print(f"  [FAIL W1 RUN] {base}.w mismatch: got {r_run.stdout!r}, expected {expected!r}")
                return False
            w1_passed += 1

        temp_file = os.path.join(repo_root, "tests", "runtime", "temp_file.txt")
        if os.path.exists(temp_file):
            os.remove(temp_file)

        print(f"  [PASS] Stage 2 w1_stage2 compiled & verified {w1_passed}/{w1_total} runtime conformance programs")
        print("==================================================")
        return True


if __name__ == "__main__":
    ok = run_bootstrap_test()
    sys.exit(0 if ok else 1)
