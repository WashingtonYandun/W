# W Documentation

The [language specification](../SPEC.md) defines W's syntax and semantics. The documents below explain the current compiler contracts and measured support boundaries.

## Language and compiler

- [Type system](TYPE_SYSTEM_DESIGN.md): nominal types, generics, invariance, and inference.
- [HIR design](HIR_DESIGN.md): typed intermediate representation and lowering rules.
- [MIR design](MIR_DESIGN.md): verified control flow, ownership transitions, and scalar ABI.
- [Ownership and lifetimes](OWNERSHIP_LIFETIME.md): ARC, copy-on-write, weak references, and cleanup.
- [Compiler error boundaries](COMPILER_ERROR_BOUNDARIES.md): diagnostic ownership across compiler stages.
- [HIR type validation](HIR_TYPE_VALIDATION.md): type invariants checked by HIR consumers.

## Runtime and supported capabilities

- [Engine parity matrix](ENGINE_PARITY_MATRIX.md): measured support across the interpreter, native backends, and W1.
- [Known limits](KNOWN_LIMITS.md): current semantic, runtime, and platform boundaries.
- [Expansion status](EXPANSION.md): functions, closures, modules, FFI, generic OOP, standard library, and LSP.
- [C FFI validation](FFI_VALIDATION.md): the SQLite pilot, ownership rules, and reproducible measurements.
- [Standard library](STDLIB.md): public library packages and their current support.

## Evidence, history, and identity

- `evidence/`: generated conformance and performance reports. Reproduction commands are documented in the relevant technical pages.
- `history/`: milestone records that describe the state at the time they were written; they do not override the current specification.
- [Brand identity](BRAND_IDENTITY.md): Wawi and the visual identity of the project.
