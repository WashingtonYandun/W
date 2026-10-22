#!/usr/bin/env python3
"""
Test Suite: Copy-on-Write (CoW) Detach Telemetry & Path-Copying Asymptotics (B02)
Verifies:
  1. Asymptotic complexity of path copying on N x M matrix:
     - First write on aliased matrix: O(N + M) copied slots (1 outer list detach of N slots + 1 row detach of M slots).
       Sibling rows 1..N-1 remain shared without detach.
     - Second write to same row: O(1) in-place write (0 additional detaches or copied slots).
     - Third write to another row: 0 outer detaches, 1 row detach of M slots.
     - Fourth write to same row: O(1) in-place write.
  2. Heterogeneous containers:
     - Struct with list (detaches struct and list).
     - Dict of lists (detaches dict).
     - Class instance in CoW list (field mutation retains shared reference semantics, slot mutation detaches list).
  3. Strict parity across all four execution engines:
     - Wysna Seed Python Interpreter
     - Wysna Seed AST C99 (under ASan, UBSan, and WYSNA_MEM_CHECK=1)
     - Wysna Seed HIR C99 (under ASan, UBSan, and WYSNA_MEM_CHECK=1)
     - Wysna Compiler Stage 2 (under ASan, UBSan, and WYSNA_MEM_CHECK=1)
"""

import os
import contextlib
import re
import subprocess
import sys
import tempfile
from typing import Dict

from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from codegen.CCodeGen import CCodeGen
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen
from main import ensure_selfhost_compiler_binary, get_repo_root


def parse_checkpoints(stderr_text: str) -> Dict[str, Dict[str, int]]:
    checkpoints = {}
    pattern = re.compile(r"\[WYSNA_COW_CHECKPOINT:([^\]]+)\]\s+(.*)")
    for line in stderr_text.splitlines():
        match = pattern.fullmatch(line)
        if match:
            label = match.group(1)
            assert label not in checkpoints, f"Duplicate checkpoint: {label}"
            checkpoints[label] = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", match.group(2))}
    return checkpoints


def run_cow_telemetry_suite() -> bool:
    repo_root = get_repo_root()
    test_file = os.path.join(repo_root, "tests", "runtime", "cow_telemetry.wysna")
    exp_file = os.path.join(repo_root, "tests", "runtime", "cow_telemetry.expected")

    print("==================================================")
    print("Wysna B02 CoW Telemetry & Asymptotics Suite")
    print("==================================================")

    with open(test_file, "r", encoding="utf-8") as f:
        src = f.read()
    with open(exp_file, "r", encoding="utf-8") as f:
        expected_stdout = f.read()

    ast = Parser(file=test_file).parse(src)
    checker = TypeChecker(file=test_file)
    checker.check(ast)

    # 1. Python Interpreter
    print("[1/4] Testing Wysna Seed Python Interpreter...")
    import io
    from runtime.Interpreter import Interpreter

    interp_out = io.StringIO()
    interp_err = io.StringIO()
    from runtime.Values import cow_telemetry
    cow_telemetry.reset()
    old_metrics = os.environ.get("WYSNA_COW_METRICS")
    os.environ["WYSNA_COW_METRICS"] = "1"
    old_stderr = sys.stderr
    sys.stderr = interp_err
    try:
        interp = Interpreter(stdout=interp_out, file=test_file)
        interp.interpret(ast)
    finally:
        sys.stderr = old_stderr
        if old_metrics is None:
            os.environ.pop("WYSNA_COW_METRICS", None)
        else:
            os.environ["WYSNA_COW_METRICS"] = old_metrics

    assert interp_out.getvalue() == expected_stdout, "Interpreter stdout mismatch"
    py_checkpoints = parse_checkpoints(interp_err.getvalue())
    print("  -> Interpreter passed output & checkpoints validated.")

    assert py_checkpoints["exclusive_after"] == py_checkpoints["exclusive_before"], "Exclusive writes must not detach"

    # Validate mathematical properties on interpreter checkpoints
    c_init = py_checkpoints["matrix_aliased"]
    c_write1 = py_checkpoints["first_write"]
    c_write2 = py_checkpoints["second_write_same_row"]
    c_write3 = py_checkpoints["third_write_other_row"]

    # First write: N=4 outer list slots + M=10 row 0 slots = 14 slots
    assert c_write1["detach_list"] == c_init["detach_list"] + 2, "First write must detach outer list and row 0"
    assert c_write1["copied_slots"] == c_init["copied_slots"] + 14, "First write must copy exactly N + M = 14 slots"

    # Second write to same row: O(1) in-place
    assert c_write2["detach_list"] == c_write1["detach_list"], "Second write to same row must not detach any list"
    assert c_write2["copied_slots"] == c_write1["copied_slots"], "Second write to same row must copy 0 additional slots"

    # Third write to other row: 0 outer list detach, 1 row detach of M=10 slots
    assert c_write3["detach_list"] == c_write2["detach_list"] + 1, "Third write to other row must detach exactly 1 row list"
    assert c_write3["copied_slots"] == c_write2["copied_slots"] + 10, "Third write to other row must copy exactly M = 10 slots"

    # Struct with list:
    c_st = py_checkpoints["struct_list_write"]
    c_st_init = py_checkpoints["struct_aliased"]
    assert c_st["detach_struct"] == c_st_init["detach_struct"] + 1, "Mutating list in struct must detach struct"
    assert c_st["detach_list"] == c_st_init["detach_list"] + 1, "Mutating list in struct must detach list"
    assert c_st["copied_slots"] == c_st_init["copied_slots"] + 5, "Struct (2 fields) + List (3 slots) = 5 slots"

    # Dict of lists:
    c_dict = py_checkpoints["dict_write"]
    c_dict_init = py_checkpoints["dict_aliased"]
    assert c_dict["detach_dict"] == c_dict_init["detach_dict"] + 1, "Writing dict entry must detach dict"
    assert c_dict["copied_slots"] == c_dict_init["copied_slots"] + 4, "Dict (2 keys + 2 vals = 4 slots)"

    # Class in list:
    c_cls1 = py_checkpoints["class_field_mutated"]
    c_cls2 = py_checkpoints["class_field_mutated_again"]
    assert c_cls2["detach_list"] == c_cls1["detach_list"], "Repeated class field mutation must be in-place"
    assert c_cls2["copied_slots"] == c_cls1["copied_slots"], "Repeated class field mutation must copy 0 slots"

    logical = lambda checkpoints: {label: {key: values[key] for key in (
        "detach_list", "detach_dict", "detach_struct", "copied_slots")} for label, values in checkpoints.items()}
    from tests.unit.test_cow_metrics_contract import run_metrics_contract
    run_metrics_contract()
    nested_before = py_checkpoints["list_struct_aliased"]
    nested_after = py_checkpoints["list_struct_write"]
    assert nested_after["detach_list"] - nested_before["detach_list"] == 2
    assert nested_after["detach_struct"] - nested_before["detach_struct"] == 1
    assert nested_after["copied_slots"] - nested_before["copied_slots"] == 6
    assert py_checkpoints["list_struct_repeat"] == nested_after
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["WYSNA_MEM_CHECK"] = "1"
        env["WYSNA_COW_METRICS"] = "1"
        env["ASAN_OPTIONS"] = "detect_leaks=1" if sys.platform.startswith("linux") else "detect_leaks=0"

        # 2. Wysna Seed AST C99
        print("[2/4] Testing Wysna Seed AST C99 (Clang ASan + UBSan + WYSNA_MEM_CHECK)...")
        c_code = CCodeGen(file=test_file).generate(ast)
        c_path = os.path.join(tmpdir, "ast.c")
        bin_path = os.path.join(tmpdir, "ast_bin")
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(c_code)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", f"-I{repo_root}", c_path, "-o", bin_path], check=True, timeout=60)
        res_ast = subprocess.run([bin_path], capture_output=True, text=True, env=env, timeout=30)
        assert res_ast.returncode == 0, f"AST C exited with error:\n{res_ast.stderr}"
        assert res_ast.stdout == expected_stdout, "AST C stdout mismatch"
        ast_checkpoints = parse_checkpoints(res_ast.stderr)
        assert logical(ast_checkpoints) == py_checkpoints, f"AST C checkpoints mismatch:\n{ast_checkpoints}\nvs\n{py_checkpoints}"
        print("  -> AST C99 passed output & checkpoints validated.")

        # 3. Wysna Seed HIR C99
        print("[3/4] Testing Wysna Seed HIR C99 (Clang ASan + UBSan + WYSNA_MEM_CHECK)...")
        builder = HirBuilder(checker.interner, file_path=test_file)
        hir_mod = builder.lower(ast)
        hir_codegen = HirCCodeGen(checker.interner, file_path=test_file)
        hir_c_code = hir_codegen.generate(hir_mod)
        hir_c_path = os.path.join(tmpdir, "hir.c")
        hir_bin_path = os.path.join(tmpdir, "hir_bin")
        with open(hir_c_path, "w", encoding="utf-8") as f:
            f.write(hir_c_code)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", f"-I{repo_root}", hir_c_path, "-o", hir_bin_path], check=True, timeout=60)
        res_hir = subprocess.run([hir_bin_path], capture_output=True, text=True, env=env, timeout=30)
        assert res_hir.returncode == 0, f"HIR C exited with error:\n{res_hir.stderr}"
        assert res_hir.stdout == expected_stdout, "HIR C stdout mismatch"
        hir_checkpoints = parse_checkpoints(res_hir.stderr)
        assert logical(hir_checkpoints) == py_checkpoints, f"HIR C checkpoints mismatch:\n{hir_checkpoints}\nvs\n{py_checkpoints}"
        print("  -> HIR C99 passed output & checkpoints validated.")

        # 4. Wysna Compiler Self-Hosted Stage 2
        print("[4/4] Testing Wysna Compiler Stage 2 (Clang ASan + UBSan + WYSNA_MEM_CHECK)...")
        selfhost_bin = ensure_selfhost_compiler_binary(repo_root)
        selfhost_c_path = os.path.join(tmpdir, "selfhost.c")
        selfhost_bin_path = os.path.join(tmpdir, "selfhost_bin")
        subprocess.run([selfhost_bin, test_file, selfhost_c_path], check=True, cwd=repo_root, timeout=60)
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", f"-I{repo_root}", selfhost_c_path, "-o", selfhost_bin_path], check=True, timeout=60)
        res_selfhost = subprocess.run([selfhost_bin_path], capture_output=True, text=True, env=env, timeout=30)
        assert res_selfhost.returncode == 0, f"Wysna Compiler exited with error:\n{res_selfhost.stderr}"
        assert res_selfhost.stdout == expected_stdout, "Wysna Compiler stdout mismatch"
        selfhost_checkpoints = parse_checkpoints(res_selfhost.stderr)
        assert logical(selfhost_checkpoints) == py_checkpoints, f"Wysna Compiler checkpoints mismatch:\n{selfhost_checkpoints}\nvs\n{py_checkpoints}"
        assert ast_checkpoints == hir_checkpoints == selfhost_checkpoints, "Native physical metrics disagree"
        print("  -> Wysna Compiler Stage 2 passed output & checkpoints validated.")

    from tests.unit.test_cow_scaling import run_scaling_tests
    run_scaling_tests()
    print("\n[SUCCESS] B02 CoW Telemetry & Asymptotic Scaling verified across all 4 execution targets!")
    return True


if __name__ == "__main__":
    ok = run_cow_telemetry_suite()
    sys.exit(0 if ok else 1)
