# W MIR: Verified Intermediate Representation

W0's default native pipeline is checked AST → typed and verified HIR → C99 → system compiler. `w emit-c` and `w build` use this HIR backend; `--backend=ast` selects the secondary AST emitter, and W1 is an independent self-hosted compiler. The `w mir path.w` command separately lowers checked HIR to MIR, verifies it, and prints the result as JSON. MIR currently has no native C emitter in the default build path.

## Representation

`mir/Nodes.py` defines modules, functions, typed slots, physical layouts, operations, basic blocks, and `goto`, `branch`, `return`, and `unreachable` terminators. MIR uses mutable slots; it is **not SSA**. Its operands are resolved identities and projections, not AST/HIR nodes or C fragments. Every operation preserves its source location.

Fields use offsets in the complete layout, including inherited fields. Mutable paths capture indices and class identity before evaluating the RHS, then resolve the slot afterward; they do not retain element pointers that a reallocation could invalidate. Patterns become predicates and branches. Narrowing an error union requires a successful check that dominates its use.

## Effects and ownership

`clone` retains, `store` moves, and `release` frees. Constructors, calls, reads, writes, and checks have explicit effect categories. Calls declare consumed operands. Managed parameters are borrowed; results are owned. Lowering inserts LIFO cleanup on normal exits, returns, propagation, `break`, and `continue`. Escaping values are protected before cleanup.

`mir/Verifier.py` checks identities, the type arena, signatures, offsets, storage, arity, effects, and successors. Dataflow intersects definitely initialized slots and joins possibly live references at joins and backedges. It rejects reads from consumed values, moves from borrowed values, and returns with owned references still pending. This verified representation is exposed by `w mir`; it is not the default native backend and does not prove the C helpers correct or track external `opaque` handles.

## Storage and ABI

Local variables, parameters, and returns of type `int`, `float`, and `bool` use `int64_t`, `double`, and `bool`. Internal counters and predicates are scalars as well. Globals, strings, lists, tuples, structs, objects, optionals, and results still use `WVal`. Adapters convert at function-value, closure, and virtual-dispatch boundaries; the public helper and FFI ABI remains `WVal`.

There are no specialized lists or unboxed payload layouts. The tagged value occupies 48 bytes in the measured arm64 ABI; converting a scalar to a collection element boxes it again. Effect classification is conservative and does not perform interprocedural purity analysis.

## Ranges

`for item in start..end` and `..=` capture bounds once, from left to right, validate the range size, and use a counter without creating a list. The 100-million-element limit applies even when the loop body immediately executes `break`. An inclusive range ending at `INT64_MAX` keeps the existing error behavior. Ranges used as values remain lists with CoW semantics; W does not add a range type.

W1 recognizes direct ranges in its parser. A parenthesized range expression may use the materialized-list path. Public semantics are the same, but this optimization is not applied uniformly to equivalent syntax.

## Verification and limits

`tests/unit/test_mir.py` mutates valid MIR to confirm that the verifier rejects invalid control flow, references, layouts, storage, runtime signatures, effects, and error-union narrowing proofs. The conformance suite covers range bounds and overflow across supported engines. CI runs the compiler matrix described in [Engine Support and Corpus Coverage](ENGINE_PARITY_MATRIX.md).

MIR verification covers the compiler-generated representation and its modeled ownership flow. It does not prove runtime helper correctness, external `opaque` resource ownership, or behavior outside the tested corpus. Performance measurements for the executable compiler backends are workload and platform dependent; see the repository benchmark tooling for reproducible runs.
