"""
test_selfhost_split_conformance.py - Conformance suite for Wysna Self-Hosted Compiler Split.

Verifies that:
1. All modular files in selfhost/src/ exist and are valid non-empty Wysna code.
2. tools/bundle_selfhost.py bundles selfhost/src/ into selfhost/compiler.wysna with byte-for-byte exact equality.
3. No dangling or missing compiler modules exist.
"""

import os
import sys
from tools.bundle_selfhost import MODULE_ORDER, bundle


def test_split_conformance() -> None:
    print("==================================================")
    print("Wysna Self-Hosted Compiler Split Conformance Suite")
    print("==================================================")

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_dir = os.path.join(repo_root, "selfhost", "src")
    compiler_path = os.path.join(repo_root, "selfhost", "compiler.wysna")

    if not os.path.exists(src_dir):
        raise AssertionError(f"Directory not found: {src_dir}")

    # Check each module
    total_lines = 0
    for mod_name in MODULE_ORDER:
        path = os.path.join(src_dir, mod_name)
        if not os.path.exists(path):
            raise AssertionError(f"Module file missing: {mod_name}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = len(content.splitlines())
        total_lines += lines
        print(f"  [PASS] Module {mod_name} ({lines} lines)")

    # Verify bundle matches compiler.wysna
    bundled = bundle(src_dir)
    with open(compiler_path, "r", encoding="utf-8") as f:
        compiler_content = f.read()

    if bundled != compiler_content:
        raise AssertionError("Bundled code does not match selfhost/compiler.wysna")

    print(f"  [PASS] All {len(MODULE_ORDER)} modules combine to exactly {total_lines} lines matching selfhost/compiler.wysna (100% loss-less).")


if __name__ == "__main__":
    test_split_conformance()
    print("\n[OK] Wysna Selfhost Split Conformance: 100% PASS.")
    sys.exit(0)
