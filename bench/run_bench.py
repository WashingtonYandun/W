import io
import os
import platform
import subprocess
import sys
import tempfile
import time
from typing import Dict, List
from parser.Parser import Parser
from checker.TypeChecker import TypeChecker
from runtime.Interpreter import Interpreter
from codegen.CCodeGen import CCodeGen

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
    print("W Language Benchmark Harness v0.1.2 (W0 Interpreter vs W0 C99 Native vs W1 Self-Hosted C99)")
    print("=========================================================================================================")
    header = (
        f"{'Benchmark':<20} | {'W0 Interp (ms)':>14} | {'W0 Compile (ms)':>15} | "
        f"{'W0 C99 (ms)':>11} | {'W1 Compile (ms)':>15} | {'W1 C99 (ms)':>11} | {'Bin (KB)':>8} | {'Speedup':>8}"
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

            # 2. W0 C99 Native compile + execution timing
            w0_c_path = os.path.join(work_dir, f"w0_{fname}.c")
            w0_bin_path = os.path.join(work_dir, f"w0_{fname}_bin")
            t_c0 = time.perf_counter()
            ast_c0 = Parser(file=path).parse(source)
            TypeChecker(file=path).check(ast_c0)
            c0_code = CCodeGen(file=path).generate(ast_c0)
            with open(w0_c_path, "w", encoding="utf-8") as cf:
                cf.write(c0_code)
            subprocess.run(
                ["cc", "-std=c99", "-O2", f"-I{repo_root}", w0_c_path, "-o", w0_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            w0_compile_ms = (time.perf_counter() - t_c0) * 1000.0

            # Warmup run to avoid OS first-exec loader/Gatekeeper latency
            subprocess.run([w0_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            t_r0 = time.perf_counter()
            r0_proc = subprocess.run([w0_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            w0_c99_ms = (time.perf_counter() - t_r0) * 1000.0
            assert r0_proc.stdout == interp_out, f"W0 C99 output mismatch on {fname}"

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
                ["cc", "-std=c99", "-O2", f"-I{repo_root}", w1_c_path, "-o", w1_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            w1_compile_ms = (time.perf_counter() - t_c1) * 1000.0

            subprocess.run([w1_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            t_r1 = time.perf_counter()
            r1_proc = subprocess.run([w1_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            w1_c99_ms = (time.perf_counter() - t_r1) * 1000.0
            assert r1_proc.stdout == interp_out, f"W1 C99 output mismatch on {fname}"

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
                f"{w0_c99_ms:>11.2f} | {w1_compile_ms:>15.2f} | {w1_c99_ms:>11.2f} | "
                f"{bin_kb:>8.1f} | {speedup:>7.1f}x"
            )

    print("=========================================================================================================")

    if update_baseline:
        baseline_path = os.path.join(bench_dir, "BASELINE.md")
        lines: List[str] = [
            "# W Language Performance Baseline (`v0.1.2`)",
            "",
            f"- **Platform:** `{platform.system()} {platform.release()} ({platform.machine()})`",
            f"- **Python Runtime (W0):** `Python {platform.python_version()}`",
            "- **C99 Optimization Flag:** `-std=c99 -O2`",
            "- **Equivalence Check:** `stdout(W0 Interpreter) == stdout(W0 C99) == stdout(W1 C99)` verified on all 10 benchmarks.",
            "",
            "| Benchmark | W0 Interp (ms) | W0 Compile (ms) | W0 C99 Exec (ms) | W1 Compile (ms) | W1 C99 Exec (ms) | Native Binary (KB) | Native Speedup |",
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
