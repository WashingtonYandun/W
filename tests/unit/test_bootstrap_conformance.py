import glob
import hashlib
import os
import subprocess
import sys
import tempfile
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from codegen.CCodeGen import CCodeGen
from tests.engine_harness import EngineResult, compare, diagnostic, unsupported_reason


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def run_bootstrap_test() -> bool:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    compiler_src_path = os.path.join(repo_root, "selfhost", "compiler.wysna")

    print("==================================================")
    print("Wysna Self-Hosting Bootstrap Suite (SPEC 11)")
    print("==================================================")

    with open(compiler_src_path, "r", encoding="utf-8") as f:
        src = f.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Stage 0 (Wysna Seed Python Compiler -> compiler0.c -> stage1 binary)
        ast = Parser(file=compiler_src_path).parse(src)
        TypeChecker(file=compiler_src_path).check(ast)
        c0_code = CCodeGen(file=compiler_src_path).generate(ast)

        compiler0_c = os.path.join(tmpdir, "compiler0.c")
        stage1_bin = os.path.join(tmpdir, "stage1")
        with open(compiler0_c, "w", encoding="utf-8") as f:
            f.write(c0_code)

        res1 = subprocess.run(
            [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", compiler0_c, "-o", stage1_bin],
            timeout=120, capture_output=True,
            text=True
        )
        if res1.returncode != 0:
            print(f"[FAIL] Stage 0 -> Stage 1 C compilation failed:\n{res1.stderr}")
            return False
        print("  [PASS] Stage 0: Wysna Seed compiled selfhost/compiler.wysna -> compiler0.c -> stage1")

        # 2. Stage 1 (stage1 native binary -> compiler1.c -> stage2 binary)
        compiler1_c = os.path.join(tmpdir, "compiler1.c")
        stage2_bin = os.path.join(tmpdir, "stage2")
        run1 = subprocess.run([stage1_bin, compiler_src_path, compiler1_c], timeout=120, capture_output=True, text=True)
        if run1.returncode != 0 or not os.path.exists(compiler1_c):
            print(f"[FAIL] Stage 1 execution failed:\n{run1.stderr}\n{run1.stdout}")
            return False

        res2 = subprocess.run(
            [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", compiler1_c, "-o", stage2_bin],
            timeout=120, capture_output=True,
            text=True
        )
        if res2.returncode != 0:
            print(f"[FAIL] Stage 1 -> Stage 2 C compilation failed:\n{res2.stderr}")
            return False
        print("  [PASS] Stage 1: stage1 compiled selfhost/compiler.wysna -> compiler1.c -> stage2")

        # 3. Stage 2 (stage2 native binary -> compiler2.c)
        compiler2_c = os.path.join(tmpdir, "compiler2.c")
        run2 = subprocess.run([stage2_bin, compiler_src_path, compiler2_c], timeout=120, capture_output=True, text=True)
        if run2.returncode != 0 or not os.path.exists(compiler2_c):
            print(f"[FAIL] Stage 2 execution failed:\n{run2.stderr}\n{run2.stdout}")
            return False
        print("  [PASS] Stage 2: stage2 compiled selfhost/compiler.wysna -> compiler2.c")

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
        w_files = sorted(glob.glob(os.path.join(repo_root, "tests", "runtime", "*.wysna")))
        selfhost_passed = 0
        selfhost_total = 0
        for w_file in w_files:
            exp_file = w_file[:-6] + ".expected"
            if not os.path.exists(exp_file):
                continue
            reason = unsupported_reason(os.path.relpath(w_file, repo_root), 'selfhost') or unsupported_reason(os.path.relpath(w_file, repo_root), 'w1')
            if reason:
                print(f'  [UNSUPPORTED SELFHOST] {os.path.relpath(w_file, repo_root)}: {reason}')
                continue
            selfhost_total += 1
            with open(exp_file, "r", encoding="utf-8") as ef:
                expected = ef.read()
            base = os.path.basename(w_file)[:-6]
            out_c = os.path.join(tmpdir, f"selfhost_{base}.c")
            out_bin = os.path.join(tmpdir, f"selfhost_{base}")

            r_selfhost = subprocess.run([stage2_bin, w_file, out_c], timeout=120, capture_output=True, text=True, cwd=repo_root)
            if r_selfhost.returncode != 0:
                print(f"  [FAIL SELFHOST] {base}.wysna compile failed: {r_selfhost.stderr}")
                return False
            r_cc = subprocess.run([os.environ.get("CC", "cc"), "-std=c99", f"-I{repo_root}", out_c, "-o", out_bin], timeout=120, capture_output=True, text=True)
            if r_cc.returncode != 0:
                print(f"  [FAIL SELFHOST CC] {base}.c failed: {r_cc.stderr}")
                return False
            r_run = subprocess.run([out_bin], timeout=30, capture_output=True, text=True, cwd=repo_root)
            result = EngineResult(
                'selfhost', stdout=r_run.stdout, stderr=r_run.stderr, exit_code=r_run.returncode,
                runtime_ok=r_run.returncode == 0, diag_code=diagnostic(r_run.stderr),
            )
            ok, detail = compare([result], expected)
            if not ok:
                print(f"  [FAIL SELFHOST RUN] {base}.wysna mismatch: {detail}")
                return False
            selfhost_passed += 1

        temp_file = os.path.join(repo_root, "tests", "runtime", "temp_file.txt")
        if os.path.exists(temp_file):
            os.remove(temp_file)

        print(f"  [PASS] Stage 2 stage2 compiled & verified {selfhost_passed}/{selfhost_total} runtime conformance programs")
        print("==================================================")
        return True


def test_bootstrap():
    assert run_bootstrap_test()


if __name__ == "__main__":
    ok = run_bootstrap_test()
    sys.exit(0 if ok else 1)
