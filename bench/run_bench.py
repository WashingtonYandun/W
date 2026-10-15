"""
bench/run_bench.py - W Language Benchmark Harness v0.2.0.

Benchmarks:
1. W0 Interpreter
2. W0 Typed HIR C99 Native (Default C06 backend)
3. W1 Self-Hosted Stage-2 Native

Runs warmups and computes median timings across multiple samples to eliminate OS scheduling jitter.
"""

import io
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from hir.HirBuilder import HirBuilder
from hir.HirCCodeGen import HirCCodeGen

BENCHMARK_ORDER: List[str] = [
    "arithmetic.w",
    "function_calls.w",
    "list_iteration.w",
    "list_copy.w",
    "list_mutation.w",
    "nested_cow.w",
    "string_unicode.w",
    "structs.w",
    "objects.w",
    "dynamic_dispatch.w",
]


def run_benchmark_suite(repo_root: str, w1_bin: str, update_baseline: bool = False) -> bool:
    bench_dir = os.path.join(repo_root, "bench")
    rows: List[Dict[str, object]] = []

    print("=========================================================================================================")
    print("W Language Benchmark Harness v0.2.0 (W0 Interpreter vs W0 Typed HIR C99 vs W1 Self-Hosted C99)")
    print("=========================================================================================================")
    header = (
        f"{'Benchmark':<20} | {'W0 Interp (ms)':>14} | {'W0 Compile (ms)':>15} | "
        f"{'W0 HIR C99(ms)':>14} | {'W1 Compile (ms)':>15} | {'W1 C99 (ms)':>11} | {'Bin (KB)':>8} | {'Speedup':>8}"
    )
    print(header)
    print("-" * len(header))

    with tempfile.TemporaryDirectory() as work_dir:
        for fname in BENCHMARK_ORDER:
            path = os.path.join(bench_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()

            # 1. W0 Interpreter timing
            old_stdout = sys.stdout
            buf_out = io.StringIO()
            sys.stdout = buf_out
            t0 = time.perf_counter()
            try:
                ast = Parser(file=path).parse(source)
                TypeChecker(file=path).check(ast)
                Interpreter(file=path).interpret(ast)
            finally:
                sys.stdout = old_stdout
            w0_interp_ms = (time.perf_counter() - t0) * 1000.0
            interp_out = buf_out.getvalue()

            # 2. W0 Typed HIR C99 Native compile + execution timing
            w0_c_path = os.path.join(work_dir, f"w0_{fname}.c")
            w0_bin_path = os.path.join(work_dir, f"w0_{fname}_bin")
            t_c0 = time.perf_counter()
            ast_c0 = Parser(file=path).parse(source)
            tc_c0 = TypeChecker(file=path)
            tc_c0.check(ast_c0)
            builder = HirBuilder(tc_c0.interner, file_path=path)
            hir_mod = builder.lower(ast_c0)
            codegen = HirCCodeGen(tc_c0.interner, file_path=path)
            c0_code = codegen.generate(hir_mod)

            with open(w0_c_path, "w", encoding="utf-8") as cf:
                cf.write(c0_code)
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", w0_c_path, "-o", w0_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            w0_compile_ms = (time.perf_counter() - t_c0) * 1000.0

            # Warmup + 3 sample median execution
            subprocess.run([w0_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            r0_times = []
            r0_proc = None
            for _ in range(3):
                t_r0 = time.perf_counter()
                r0_proc = subprocess.run([w0_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
                r0_times.append((time.perf_counter() - t_r0) * 1000.0)
            w0_c99_ms = statistics.median(r0_times)
            assert r0_proc is not None and r0_proc.stdout == interp_out, f"W0 C99 output mismatch on {fname}"

            # 3. W1 Stage-2 Self-Hosted C99 Native compile + execution timing
            w1_c_path = os.path.join(work_dir, f"w1_{fname}.c")
            w1_bin_path = os.path.join(work_dir, f"w1_{fname}_bin")
            t_c1 = time.perf_counter()
            subprocess.run(
                [w1_bin, path, w1_c_path],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", w1_c_path, "-o", w1_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            w1_compile_ms = (time.perf_counter() - t_c1) * 1000.0

            subprocess.run([w1_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            r1_times = []
            r1_proc = None
            for _ in range(3):
                t_r1 = time.perf_counter()
                r1_proc = subprocess.run([w1_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
                r1_times.append((time.perf_counter() - t_r1) * 1000.0)
            w1_c99_ms = statistics.median(r1_times)
            assert r1_proc is not None and r1_proc.stdout == interp_out, f"W1 C99 output mismatch on {fname}"

            bin_kb = os.path.getsize(w1_bin_path) / 1024.0
            speedup = w0_interp_ms / max(w1_c99_ms, 0.01)

            row = {
                "name": fname,
                "w0_interp_ms": w0_interp_ms,
                "w0_compile_ms": w0_compile_ms,
                "w0_c99_ms": w0_c99_ms,
                "w1_compile_ms": w1_compile_ms,
                "w1_c99_ms": w1_c99_ms,
                "bin_kb": bin_kb,
                "speedup": speedup,
            }
            rows.append(row)

            print(
                f"{fname:<20} | {w0_interp_ms:>14.2f} | {w0_compile_ms:>15.2f} | "
                f"{w0_c99_ms:>14.2f} | {w1_compile_ms:>15.2f} | {w1_c99_ms:>11.2f} | "
                f"{bin_kb:>8.1f} | {speedup:>7.1f}x"
            )

    print("=========================================================================================================")

    if update_baseline:
        baseline_path = os.path.join(bench_dir, "BASELINE.md")
        lines: List[str] = [
            "# W Language Performance Baseline (`v0.2.0`)",
            "",
            f"- **Platform:** `{platform.system()} {platform.release()} ({platform.machine()})`",
            f"- **Python Runtime (W0):** `Python {platform.python_version()}`",
            "- **C99 Optimization Flag:** `-std=c99 -O2`",
            "- **W0 Backend:** Default Typed HIR C99 (`hir/HirCCodeGen.py`)",
            "- **Equivalence Check:** `stdout(W0 Interpreter) == stdout(W0 Typed HIR C99) == stdout(W1 C99)` verified on all 10 benchmarks.",
            "- **Timing Methodology:** Median of 3 iterations with separate warmup run to eliminate OS scheduling jitter.",
            "",
            "| Benchmark | W0 Interp (ms) | W0 Compile (ms) | W0 HIR C99 Exec (ms) | W1 Compile (ms) | W1 C99 Exec (ms) | Native Binary (KB) | Native Speedup |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in rows:
            lines.append(
                f"| `{r['name']}` | {r['w0_interp_ms']:.2f} | {r['w0_compile_ms']:.2f} | "
                f"{r['w0_c99_ms']:.2f} | {r['w1_compile_ms']:.2f} | {r['w1_c99_ms']:.2f} | "
                f"{r['bin_kb']:.1f} | **{r['speedup']:.1f}x** |"
            )
        lines.append("")
        with open(baseline_path, "w", encoding="utf-8") as bf:
            bf.write("\n".join(lines))
        print(f"Updated baseline metrics in {baseline_path}")

    return True


if __name__ == "__main__":
    w1_bin_path = os.path.join(str(ROOT), ".w_cache", "w1_stage2")
    update_base = "--update-baseline" in sys.argv
    run_benchmark_suite(str(ROOT), w1_bin_path, update_baseline=update_base)
