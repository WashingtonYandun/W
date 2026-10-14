# B02 — Copy-on-Write Detach Telemetry & Real Cost Measurement

Status: implemented; verification results and PR are recorded in the Engineering Brain.
Branch: feat/b02-cow-telemetry, based on develop at b734ea4.

## Implemented Telemetry & Instrumentation

1. **C99 Single-Header Runtime (`runtime/w_runtime.h`)**:
   - Added global detach metrics counters:
     - `w_g_cow_detach_list`: increments on each list buffer clone.
     - `w_g_cow_detach_dict`: increments on each dictionary buffer clone.
     - `w_g_cow_detach_struct`: increments on each struct buffer clone.
     - `w_g_cow_copied_slots`: counts total element slots copied across detaches.
     - `w_g_cow_copied_bytes`: measures exact heap bytes allocated during detachment (buffer metadata + capacity payload).
     - `w_g_cow_alloc_count`: counts distinct `malloc` invocations performed during detachment.
   - Added `w_cow_reset_stats()` to reset metrics at test boundaries.
   - Added `W_COW_METRICS=1` environment variable support to emit final CoW metrics summary on `w_runtime_cleanup()`.
   - Instrumented `w_builtin_eprint` to detect `__COW_CHECKPOINT__:<label>` markers and emit instant point-in-time telemetry snapshots without polluting standard program stdout.

2. **W0 Python Tree-Walking Interpreter (`runtime/Values.py`, `runtime/Environment.py`, `runtime/Interpreter.py`)**:
   - Added `CowTelemetry` tracker class with bit-for-bit parity with the C runtime.
   - Instrumented `WList.ensure_unique()`, `WDict.ensure_unique()`, and `WStructInstance.ensure_unique()`.
   - Added `__COW_CHECKPOINT__:<label>` support in `eprint_fn`.
   - Added `atexit` handler for `W_COW_METRICS=1` environment variable.
   - Aligned buffer capacity scaling rules between Python and C runtime (`cap = n if n > 4 else 4`).

## Asymptotic Verification & Path Copying Mechanics

Validated via `tests/runtime/cow_telemetry.w` and `test_cow_telemetry.py` across all four targets:

1. **$N \times M$ Matrix ($N=4, M=10$) with Alias**:
   - Baseline checkpoint: 0 detaches, 0 slots copied.
   - **First write to cell $(0, 0)$**: Detaches outer list ($N=4$ slots) and row 0 list ($M=10$ slots). Total copied slots = exactly $N + M = 14$ slots ($O(N + M)$). Sibling rows $1, 2, 3$ remain shared with the snapshot at zero detachment cost.
   - **Second write to cell $(0, 1)$ (same row)**: 0 additional detaches, 0 additional copied slots ($O(1)$ in-place mutation on exclusive buffer).
   - **Third write to cell $(1, 0)$ (other row)**: Outer list is already exclusive (0 detaches), row 1 detaches ($M=10$ slots). Total copied slots = 24. Sibling rows $2, 3$ remain shared.

2. **Heterogeneous Containers**:
   - **Struct containing List**: Modifying a nested list element through an aliased struct triggers 1 struct detach (2 slots) and 1 list detach (3 slots). Total copied slots = 5.
   - **Dict of Lists**: Assigning to a dictionary entry triggers 1 dict detach (4 slots = 2 keys + 2 values).
   - **Class Instance in CoW List (Reference Semantics Boundary)**:
     - Mutating a field of a class instance (`trackers[0].count = 42`) in an aliased list detaches the outer list buffer (to project the mutable lvalue path), but does NOT clone the class instance. Both aliases observe `count == 42`.
     - Repeated field mutations on elements (`trackers[1].count = 84`) occur in-place with 0 additional detaches.

## Verification Evidence

- `test_cow_telemetry.py` passes with bit-for-bit parity across all four targets:
  - W0 Python Interpreter: PASS
  - W0 AST C99 (Clang ASan + UBSan + `W_MEM_CHECK=1`): PASS
  - W0 HIR C99 (Clang ASan + UBSan + `W_MEM_CHECK=1`): PASS
  - W1 Stage-2 Native Compiler (Clang ASan + UBSan + `W_MEM_CHECK=1`): PASS
- Full conformance suite: `ALL 384/384 CONFORMANCE, EXAMPLES & SELF-HOSTING TESTS PASSED (100%)`.
- Differential fuzzing suite: `79/79 differential cases passed`.
- Three-stage bootstrap fixed-point: SHA256 matches across `compiler0.c`, `compiler1.c`, and `compiler2.c`.

## Next Milestones

- **B03**: Reference cycle handling and weak references for class instances (`Weak[T]`).
- **B04**: Mandatory CI workflows with Linux Clang ASan+UBSan+LSan and GCC matrix gates.
