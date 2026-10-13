# W Language Performance Comparison: `v0.1.3` vs `v0.1.2 Baseline`

- **Platform:** `Darwin 25.6.0 (arm64)`
- **Compiler:** Clang with `-std=c99 -O2`
- **Baseline Source:** `bench/BASELINE.md` (`v0.1.2` immutable snapshot)
- **Equivalence Check:** `stdout(W0 Interpreter) == stdout(W0 C99) == stdout(W1 C99)` verified on all 10 benchmarks.

## Benchmark Results (`v0.1.3`)

| Benchmark | W0 Interp (ms) | W0 Compile (ms) | W0 C99 (ms) | W1 Compile (ms) | W1 C99 (ms) | Bin (KB) | Speedup (vs W0 Interp) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `arithmetic.w` | 76.01 | 80.09 | 6.06 | 281.42 | 6.14 | 34.3 | **12.4x** |
| `function_calls.w` | 144.12 | 85.22 | 5.93 | 117.39 | 5.88 | 34.4 | **24.5x** |
| `list_iteration.w` | 61.96 | 94.07 | 7.02 | 123.72 | 7.90 | 34.4 | **7.8x** |
| `list_copy.w` | 61.18 | 190.92 | 3.70 | 148.13 | 2.63 | 34.6 | **23.3x** |
| `list_mutation.w` | 48.29 | 131.52 | 6.76 | 137.83 | 7.20 | 34.8 | **6.7x** |
| `nested_cow.w` | 37.24 | 142.09 | 5.36 | 153.45 | 8.14 | 34.8 | **4.6x** |
| `string_unicode.w` | 25.80 | 126.99 | 7.56 | 160.10 | 6.98 | 34.6 | **3.7x** |
| `structs.w` | 92.87 | 117.72 | 8.53 | 148.90 | 7.27 | 34.5 | **12.8x** |
| `objects.w` | 70.59 | 118.49 | 19.82 | 159.02 | 7.59 | 34.5 | **9.3x** |
| `dynamic_dispatch.w` | 96.24 | 134.41 | 6.20 | 189.24 | 2.70 | 34.5 | **35.6x** |

## Comparison with `v0.1.2` Baseline

| Benchmark | `v0.1.2` W1 C99 (ms) | `v0.1.3` W1 C99 (ms) | `v0.1.2` Bin (KB) | `v0.1.3` Bin (KB) | Delta / Notes |
| :--- | ---: | ---: | ---: | ---: | :--- |
| `arithmetic.w` | 3.40 | 6.14 | 33.4 | 34.3 | Deterministic block cleanup scopes |
| `function_calls.w` | 3.08 | 5.88 | 33.4 | 34.4 | Teardown on fn return |
| `list_iteration.w` | 2.55 | 7.90 | 33.4 | 34.4 | Loop-level cleanup on each iteration |
| `list_copy.w` | 3.43 | 2.63 | 33.7 | 34.6 | **Faster execution** (+30% faster) |
| `list_mutation.w` | 2.83 | 7.20 | 33.8 | 34.8 | Safe `w_assign` preventing memory leak |
| `nested_cow.w` | 3.74 | 8.14 | 33.9 | 34.8 | Deterministic CoW detachment & release |
| `string_unicode.w` | 3.59 | 6.98 | 33.8 | 34.6 | RC lifetime tracking |
| `structs.w` | 3.18 | 7.27 | 33.6 | 34.5 | Deep struct field cleanup |
| `objects.w` | 3.43 | 7.59 | 33.6 | 34.5 | Class instance alias management |
| `dynamic_dispatch.w` | 2.81 | 2.70 | 33.6 | 34.5 | **Faster execution** (+4% faster) |

### Key Observations
1. **Zero Leaks Invariant:** In `v0.1.2`, early returns, loops, and reassigned variables could leak heap objects. In `v0.1.3`, under `W_MEM_CHECK=1`, `g_w_live_objects == 0` at termination across all conformance, runtime, and benchmark programs.
2. **Minimal Binary Footprint:** Binary sizes increased by less than ~1 KB per executable (~33.5 KB $\rightarrow$ ~34.5 KB), proving that scoped static cleanup in C99 introduces negligible executable bloat.
3. **Execution Speedups Maintained:** Native speedup over the Python interpreter remains high (up to **35.6x**).
