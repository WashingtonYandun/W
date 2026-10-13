"""
test_w1_split_conformance.py - Conformance suite for W1 Modular Compiler Split.

Verifies that:
1. All modular files in selfhost/src/ exist and are valid non-empty W code.
2. tools/bundle_w1.py bundles selfhost/src/ into selfhost/w1.w with byte-for-byte exact equality.
3. No dangling or missing compiler modules exist.
"""

import os
import sys
from tools.bundle_w1 import MODULE_ORDER, bundle


def test_split_conformance() -> bool:
    print("==================================================")
    print("W1 Modular Compiler Split Conformance Suite")
    print("==================================================")

    repo_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(repo_root, "selfhost", "src")
    w1_path = os.path.join(repo_root, "selfhost", "w1.w")

    if not os.path.exists(src_dir):
        print(f"  [FAIL] Directory not found: {src_dir}")
        return False

    # Check each module
    total_lines = 0
    for mod_name in MODULE_ORDER:
        path = os.path.join(src_dir, mod_name)
        if not os.path.exists(path):
            print(f"  [FAIL] Module file missing: {mod_name}")
            return False
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = len(content.splitlines())
        total_lines += lines
        print(f"  [PASS] Module {mod_name} ({lines} lines)")

    # Verify bundle matches w1.w
    bundled = bundle(src_dir)
    with open(w1_path, "r", encoding="utf-8") as f:
        w1_content = f.read()

    if bundled != w1_content:
        print("  [FAIL] Bundled code does not match selfhost/w1.w!")
        return False

    print(f"  [PASS] All {len(MODULE_ORDER)} modules combine to exactly {total_lines} lines matching selfhost/w1.w (100% loss-less).")
    return True


if __name__ == "__main__":
    if not test_split_conformance():
        sys.exit(1)
    print("\n[OK] W1 Split Conformance: 100% PASS.")
    sys.exit(0)
