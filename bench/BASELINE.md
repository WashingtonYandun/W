# W Language Performance Baseline (`v0.2.0`)

- **Platform:** `Darwin 25.6.0 (arm64)`
- **Python Runtime (W0):** `Python 3.14.7`
- **C99 Optimization Flag:** `-std=c99 -O2`
- **W0 Backend:** Default Typed HIR C99 (`hir/HirCCodeGen.py`)
- **Equivalence Check:** `stdout(W0 Interpreter) == stdout(W0 Typed HIR C99) == stdout(W1 C99)` verified on all 10 benchmarks.
- **Timing Methodology:** Median of 3 iterations with separate warmup run to eliminate OS scheduling jitter.

| Benchmark | W0 Interp (ms) | W0 Compile (ms) | W0 HIR C99 Exec (ms) | W1 Compile (ms) | W1 C99 Exec (ms) | Native Binary (KB) | Native Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `arithmetic.w` | 108.66 | 219.01 | 5.64 | 129.71 | 7.09 | 36.3 | **15.3x** |
| `function_calls.w` | 155.35 | 106.56 | 6.07 | 126.63 | 6.87 | 36.3 | **22.6x** |
| `list_iteration.w` | 63.30 | 126.56 | 5.98 | 139.86 | 6.44 | 36.6 | **9.8x** |
| `list_copy.w` | 73.96 | 144.09 | 3.39 | 156.39 | 5.09 | 36.9 | **14.5x** |
| `list_mutation.w` | 71.05 | 157.23 | 7.36 | 167.52 | 6.85 | 53.4 | **10.4x** |
| `nested_cow.w` | 55.83 | 184.36 | 4.88 | 183.84 | 6.73 | 53.8 | **8.3x** |
| `string_unicode.w` | 18.80 | 174.15 | 6.14 | 184.22 | 2.95 | 52.8 | **6.4x** |
| `structs.w` | 93.43 | 131.68 | 6.57 | 159.28 | 6.44 | 36.9 | **14.5x** |
| `objects.w` | 78.41 | 155.55 | 6.08 | 160.81 | 6.12 | 36.8 | **12.8x** |
| `dynamic_dispatch.w` | 104.07 | 138.03 | 5.26 | 148.44 | 6.20 | 37.0 | **16.8x** |
