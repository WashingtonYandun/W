# HIR verification boundary

HIR is verified after lowering and again before C emission. Invalid internal input raises W9999 at `hir-verification`; unsupported backend nodes never silently become unit.

## Verified contracts

- Required TypeIds and recursive type components belong to the current interner and are neither TYPE_ERROR nor malformed IDs. Recursive nominal types are supported.
- Declarations, parameters, fields, blocks, tails, match arms, guards and typed patterns are traversed. Active-path cycle detection rejects cyclic nodes and containers while allowing shared acyclic nodes.
- Break/continue require loops; returns require functions; conditions and guards are bool. Function boundaries reset loop context.
- Literals, operators, ranges, tuples and collection metadata agree with their interned types. Collection elements, bindings, assignments and returns satisfy checked assignability.
- Lexical local references resolve with matching types. Direct functions, class/inherited methods, interface methods and collection methods resolve with checked arity, arguments and result types.
- Class and struct constructors resolve; struct fields are complete and unique. Enum constructors resolve to declared variants with matching indices and payload types. Builtin constructor families are canonical.
- Propagation agrees with the outer optional/result channel and the enclosing return type. Match patterns carry inferred types; guards retain their bindings and execution semantics.

Lowering consumes checker annotation IDs, including synthesized generic constructors, assignments and imported functions, rather than reconstructing types from mangled strings. Enum declarations retain payload metadata for independent constructor validation.

## Evidence and limits

`test_compiler_boundaries.py` mutates checked HIR and requires rejection before C emission. `test_hir_conformance.py` exercises the 52-file supported HIR corpus. `test_phase_a.py` checks canonical aliases, nested errors, guards and native sanitized execution.

This validates the current name-based HIR. It does not introduce SymbolIds, a typed module session, arena provenance tokens, an ownership proof or W1 generic parity. An in-range ID transplanted from another arena cannot be distinguished without provenance metadata. Builtin runtime helper contracts and broader ownership paths remain covered by their separate regression suites and later roadmap tasks.
