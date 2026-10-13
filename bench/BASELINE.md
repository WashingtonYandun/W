# W Language Performance Baseline (`v0.1.2`)

- **Platform:** `Darwin 25.6.0 (arm64)`
- **Python Runtime (W0):** `Python 3.14.7`
- **C99 Optimization Flag:** `-std=c99 -O2`
- **Equivalence Check:** `stdout(W0 Interpreter) == stdout(W0 C99) == stdout(W1 C99)` verified on all 10 benchmarks.

| Benchmark | W0 Interp (ms) | W0 Compile (ms) | W0 C99 Exec (ms) | W1 Compile (ms) | W1 C99 Exec (ms) | Native Binary (KB) | Native Speedup |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `arithmetic.w` | 79.36 | 532.02 | 2.78 | 89.62 | 3.40 | 33.4 | **23.3x** |
| `function_calls.w` | 122.25 | 127.74 | 2.80 | 92.81 | 3.08 | 33.4 | **39.7x** |
| `list_iteration.w` | 47.30 | 115.20 | 2.68 | 90.09 | 2.55 | 33.4 | **18.5x** |
| `list_copy.w` | 51.17 | 109.44 | 3.45 | 111.56 | 3.43 | 33.7 | **14.9x** |
| `list_mutation.w` | 51.13 | 126.14 | 3.33 | 115.42 | 2.83 | 33.8 | **18.1x** |
| `nested_cow.w` | 34.74 | 122.86 | 3.84 | 134.82 | 3.74 | 33.9 | **9.3x** |
| `string_unicode.w` | 15.94 | 123.15 | 3.44 | 112.87 | 3.59 | 33.8 | **4.4x** |
| `structs.w` | 74.74 | 97.33 | 5.71 | 110.55 | 3.18 | 33.6 | **23.5x** |
| `objects.w` | 57.77 | 104.57 | 3.57 | 112.10 | 3.43 | 33.6 | **16.8x** |
| `dynamic_dispatch.w` | 81.22 | 96.62 | 6.14 | 105.26 | 2.81 | 33.6 | **28.9x** |
