# Documentation

[The language specification](../SPEC.md) defines W syntax and semantics. The documents below describe compiler and runtime contracts.

## Compiler

- [Type system](TYPE_SYSTEM_DESIGN.md): canonical types, assignability, variance, and generic substitution.
- [HIR](HIR_DESIGN.md): typed representation and verification boundary.
- [MIR](MIR_DESIGN.md): control flow, ownership operations, layouts, and C99 emission.
- [Ownership and lifetimes](OWNERSHIP_LIFETIME.md): ARC, CoW, weak references, and cleanup.
- [Engine support](ENGINE_PARITY_MATRIX.md): tested fixture coverage across W0 and W1.
- [Known limits](KNOWN_LIMITS.md): supported boundaries and deferred language decisions.

## Runtime and libraries

- [C interoperability](FFI_VALIDATION.md): scalar ABI, opaque handles, and SQLite pilot.
- [Standard library](STDLIB.md): packages and their current contracts.
