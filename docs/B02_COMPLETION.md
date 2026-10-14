# B02 — CoW telemetry and cost measurement

Branch: feat/b02-cow-telemetry. Base: develop at b734ea4.
PR: https://github.com/WashingtonYandun/W/pull/40
Status: implementation and review corrections complete; final verification is
recorded in the PR and Engineering Brain session. Integration is pending.

## Metrics contract

Set `W_COW_METRICS=1` to emit a process summary on stderr. In this opt-in mode,
`eprint("__COW_CHECKPOINT__:<label>")` emits one checkpoint record. Only a single
string argument is recognized. Without the flag, or with multiple arguments,
eprint retains ordinary text semantics on every engine.

Native C runtime counters record:

- detach_list, detach_dict, detach_struct: actual shared-buffer detach operations.
- copied_slots: logical value slots copied (dictionary keys and values count
  separately; struct field-name pointers do not count as value slots).
- copied_bytes: bytes of initialized value slots and struct field-name pointers
  copied, derived from the compiled ABI with sizeof.
- allocated_bytes: requested heap storage for detached metadata and arrays,
  including reserved capacity. Allocator overhead is excluded.
- allocs: malloc calls performed by detaches, excluding unrelated allocation and
  later capacity growth. This is not total program allocation traffic.

The Python interpreter reports logical detaches and copied slots. It does not
claim physical byte or malloc parity with C: Python has different storage and no
C buffer capacity ABI. Counters are process-wide and reset only explicitly;
constructing interpreters for imports does not erase accumulated measurements.
Live list/dict/struct wrappers own buffer references, released when those wrappers
expire. Dead aliases no longer force phantom detaches.

## Reproducible acceptance

```sh
python3 test_cow_telemetry.py
./w test
./w test --differential 20
./w test --fuzz 100
python3 tools/bundle_w1.py --check
```

The telemetry suite includes these independent checks:

- Existing 4x10 matrix: first write copies outer N plus row M; another write to
  that row copies nothing; writing another row copies M.
- Independent dimensions (2,3), (2,17), (7,3), (7,17), multiple aliases, a fourth
  write, an additional snapshot, and further exclusive writes. Both dimensions
  vary independently; one fixed example is not described as asymptotic proof.
- Native pointer-identity assertions verify untouched sibling rows stay shared.
- Struct with list; list of structs with lists; dictionary entry replacement;
  class-reference identity inside an aliased list; side-effectful index once.
- Exclusive writes, expired aliases, and rejection of immutable/tuple mutation.
- Native ABI/capacity assertions for a popped list retaining its capacity, a grown
  dictionary and an empty struct, including zero-byte copies with nonzero storage.
- Opt-in eprint behavior, multi-argument stderr parity and import counter lifetime.

AST C, HIR C and standalone W1-emitted C run with ASan/UBSan and W_MEM_CHECK.
Linux enables LSan. The CI sanitizer jobs also run this suite with CC=clang.
Compilation and execution subprocesses have timeouts; the existing cached W1
bootstrap helper retains its own current subprocess behavior.

## Measured limits

For aliased rectangular matrices in the recorded corpus, copied value slots are
N+M on the first write, zero on an exclusive repeat, and M on a new row. Native
reserved bytes depend on capacities. Dictionary lookup remains linear in entries;
these counters do not measure lookup work or establish wall-clock complexity.

B01 keeps some constructor temporaries alive until scope exit. A separately
asserted case, `let mut nested = [[1, 2]]`, therefore copies one two-slot row on its
first native write; the interpreter copies zero after dead-alias cleanup. The
suite records this difference explicitly rather than fabricating bit-for-bit
physical parity. Shortening native temporary lifetimes is future ownership
optimization work; it must preserve B01 evaluation and cleanup guarantees.

W1 generic exclusions, strong RC cycles, allocation failure and concurrent RC
remain outside these gates. B03 addresses cycles/weak references; B04 expands
mandatory integration coverage.
