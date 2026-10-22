import os
import sys
from tests.formatter_contract import formatter_paths, verify_formatting


def run_formatter_tests() -> bool:
    files = formatter_paths()
    passed = 0
    failed = 0

    print("==========================================")
    print("Wysna Formatter Idempotence Suite")
    print("==========================================")

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            src = f.read()
        try:
            verify_formatting(src, str(fpath))
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
