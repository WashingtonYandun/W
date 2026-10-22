"""
bench/run_bench.py - Wysna Benchmark Harness.

Benchmarks:
1. Wysna Seed Interpreter
2. Wysna Seed Typed HIR C99 Native (default Seed native backend)
3. Wysna Compiler Stage-2 Native

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

# Samples per measurement, after one warmup run. Three samples cannot
# characterise an OS-scheduled process, and the two engines are now measured
# with the same protocol.
SAMPLES = 15

BENCHMARK_ORDER: List[str] = [
    "arithmetic.wysna",
    "function_calls.wysna",
    "list_iteration.wysna",
    "list_copy.wysna",
    "list_mutation.wysna",
    "nested_cow.wysna",
    "string_unicode.wysna",
    "structs.wysna",
    "objects.wysna",
    "dynamic_dispatch.wysna",
]


def run_benchmark_suite(repo_root: str, selfhost_bin: str, update_baseline: bool = False) -> bool:
    bench_dir = os.path.join(repo_root, "bench")
    rows: List[Dict[str, object]] = []

    print("=========================================================================================================")
    print("Wysna Benchmark Harness (Wysna Seed Interpreter vs Wysna Seed Typed HIR C99 vs Wysna Compiler C99)")
    print("=========================================================================================================")
    header = (
        f"{'Benchmark':<20} | {'Seed Interp(ms)':>15} | {'Seed Compile(ms)':>16} | "
        f"{'Seed HIR C99(ms)':>16} | {'Compiler Cmp(ms)':>16} | {'Compiler C99(ms)':>16} | {'Bin (KB)':>8} | "
        f"{'vs HIR':>7} | {'vs Self':>7}"
    )
    print(header)
    print("-" * len(header))

    with tempfile.TemporaryDirectory() as work_dir:
        for fname in BENCHMARK_ORDER:
            path = os.path.join(bench_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()

            # 1. Wysna Seed Interpreter timing.
            ast = Parser(file=path).parse(source)
            tc = TypeChecker(file=path)
            tc.check(ast)

            def run_interpreter() -> str:
                captured = io.StringIO()
                saved, sys.stdout = sys.stdout, captured
                try:
                    Interpreter(file=path).interpret(ast)
                finally:
                    sys.stdout = saved
                return captured.getvalue()

            interp_out = run_interpreter()
            interp_times = []
            for _ in range(SAMPLES):
                t0 = time.perf_counter()
                run_interpreter()
                interp_times.append((time.perf_counter() - t0) * 1000.0)
            seed_interp_ms = statistics.median(interp_times)

            # 2. Wysna Seed Typed HIR C99 Native compile + execution timing
            seed_c_path = os.path.join(work_dir, f"seed_{fname}.c")
            seed_bin_path = os.path.join(work_dir, f"seed_{fname}_bin")
            t_c0 = time.perf_counter()
            ast_c0 = Parser(file=path).parse(source)
            tc_c0 = TypeChecker(file=path)
            tc_c0.check(ast_c0)
            builder = HirBuilder(tc_c0.interner, file_path=path)
            hir_mod = builder.lower(ast_c0)
            codegen = HirCCodeGen(tc_c0.interner, file_path=path)
            c0_code = codegen.generate(hir_mod)

            with open(seed_c_path, "w", encoding="utf-8") as cf:
                cf.write(c0_code)
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", seed_c_path, "-o", seed_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            seed_compile_ms = (time.perf_counter() - t_c0) * 1000.0

            # Warmup + SAMPLES sample median execution
            subprocess.run([seed_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            r0_times = []
            r0_proc = None
            for _ in range(SAMPLES):
                t_r0 = time.perf_counter()
                r0_proc = subprocess.run([seed_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
                r0_times.append((time.perf_counter() - t_r0) * 1000.0)
            seed_c99_ms = statistics.median(r0_times)
            assert r0_proc is not None and r0_proc.stdout == interp_out, f"Wysna Seed C99 output mismatch on {fname}"

            # 3. Wysna Compiler Stage-2 C99 Native compile + execution timing
            selfhost_c_path = os.path.join(work_dir, f"selfhost_{fname}.c")
            selfhost_bin_path = os.path.join(work_dir, f"selfhost_{fname}_bin")
            t_c1 = time.perf_counter()
            subprocess.run(
                [selfhost_bin, path, selfhost_c_path],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=c99", "-O2", f"-I{repo_root}", selfhost_c_path, "-o", selfhost_bin_path],
                check=True,
                capture_output=True,
                text=True,
            )
            selfhost_compile_ms = (time.perf_counter() - t_c1) * 1000.0

            subprocess.run([selfhost_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
            r1_times = []
            r1_proc = None
            for _ in range(SAMPLES):
                t_r1 = time.perf_counter()
                r1_proc = subprocess.run([selfhost_bin_path], check=True, capture_output=True, text=True, cwd=repo_root)
                r1_times.append((time.perf_counter() - t_r1) * 1000.0)
            selfhost_c99_ms = statistics.median(r1_times)
            assert r1_proc is not None and r1_proc.stdout == interp_out, f"Wysna Compiler C99 output mismatch on {fname}"

            bin_kb = os.path.getsize(selfhost_bin_path) / 1024.0
            speedup_vs_hir = seed_interp_ms / max(seed_c99_ms, 0.01)
            speedup = seed_interp_ms / max(selfhost_c99_ms, 0.01)

            row = {
                "name": fname,
                "seed_interp_ms": seed_interp_ms,
                "seed_compile_ms": seed_compile_ms,
                "seed_c99_ms": seed_c99_ms,
                "selfhost_compile_ms": selfhost_compile_ms,
                "selfhost_c99_ms": selfhost_c99_ms,
                "bin_kb": bin_kb,
                "speedup": speedup,
                "speedup_vs_hir": speedup_vs_hir,
                "interp_samples_ms": interp_times,
                "seed_c99_samples_ms": r0_times,
                "selfhost_c99_samples_ms": r1_times,
            }
            rows.append(row)

            print(
                f"{fname:<20} | {seed_interp_ms:>15.2f} | {seed_compile_ms:>16.2f} | "
                f"{seed_c99_ms:>16.2f} | {selfhost_compile_ms:>16.2f} | {selfhost_c99_ms:>16.2f} | "
                f"{bin_kb:>8.1f} | {speedup_vs_hir:>6.1f}x | {speedup:>6.1f}x"
            )

    print("=========================================================================================================")

    if update_baseline:
        baseline_path = os.path.join(bench_dir, "BASELINE.md")
        lines: List[str] = [
            "# Wysna Performance Baseline",
            "",
            f"- **Platform:** `{platform.system()} {platform.release()} ({platform.machine()})`",
            f"- **Python Runtime (Wysna Seed):** `Python {platform.python_version()}`",
            "- **C99 Optimization Flag:** `-std=c99 -O2`",
            "- **Wysna Seed Backend:** Default Typed HIR C99 (`hir/HirCCodeGen.py`)",
            "- **Equivalence Check:** `stdout(Seed Interpreter) == stdout(Seed Typed HIR C99) == stdout(Wysna Compiler C99)` verified on all 10 benchmarks.",
            f"- **Timing Methodology:** Median of {SAMPLES} samples after one warmup run per benchmark.",
            "",
            "| Benchmark | Seed Interp (ms) | Seed Compile (ms) | Seed HIR C99 Exec (ms) | Compiler Compile (ms) | Compiler C99 Exec (ms) | Native Binary (KB) | Native Speedup |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in rows:
            lines.append(
                f"| `{r['name']}` | {r['seed_interp_ms']:.2f} | {r['seed_compile_ms']:.2f} | "
                f"{r['seed_c99_ms']:.2f} | {r['selfhost_compile_ms']:.2f} | {r['selfhost_c99_ms']:.2f} | "
                f"{r['bin_kb']:.1f} | **{r['speedup']:.1f}x** |"
            )
        lines.append("")
        with open(baseline_path, "w", encoding="utf-8") as bf:
            bf.write("\n".join(lines))
        print(f"Updated baseline metrics in {baseline_path}")

    return True


if __name__ == "__main__":
    from main import ensure_selfhost_compiler_binary
    selfhost_bin_path = ensure_selfhost_compiler_binary(str(ROOT))
    update_base = "--update-baseline" in sys.argv
    run_benchmark_suite(str(ROOT), selfhost_bin_path, update_baseline=update_base)
