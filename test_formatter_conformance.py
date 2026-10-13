import glob
import os
import sys
from parser.Parser import Parser
from formatter.Formatter import Formatter


def run_formatter_tests() -> bool:
    files = sorted(glob.glob("tests/formatter/*.w") + glob.glob("tests/runtime/*.w"))
    passed = 0
    failed = 0

    print("==========================================")
    print("W v0.1 Formatter Idempotence Suite")
    print("==========================================")

    fmt = Formatter()
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            ast1 = Parser(file=fpath).parse(src)
            formatted1 = fmt.format(ast1)
            ast2 = Parser(file=fpath).parse(formatted1)
            formatted2 = fmt.format(ast2)

            if formatted1 != formatted2:
                print(f"[FAIL] {os.path.basename(fpath)}: Not idempotent (fmt(fmt(x)) != fmt(x))")
                failed += 1
            else:
                passed += 1
        except Exception as e:
            print(f"[FAIL] {os.path.basename(fpath)}: Exception {e}")
            failed += 1

    print(f"[PASS] Formatter idempotence verified on {passed}/{len(files)} files")
    print("------------------------------------------")
    print(f"Formatter Summary: {passed} passed, {failed} failed")
    print("==========================================")
    return failed == 0


if __name__ == "__main__":
    ok = run_formatter_tests()
    sys.exit(0 if ok else 1)
