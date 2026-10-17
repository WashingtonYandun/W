# Documentation

[The language specification](../SPEC.md) defines W syntax and semantics. The documents below describe compiler and runtime contracts.

## Compiler

- [Type system](TYPE_SYSTEM_DESIGN.md): canonical types, assignability, variance, and generic substitution.
- [HIR](HIR_DESIGN.md): typed representation, verification boundary, and default C99 backend.
- [MIR](MIR_DESIGN.md): verified intermediate representation and current implementation boundary.
- [Ownership and lifetimes](OWNERSHIP_LIFETIME.md): ARC, CoW, weak references, and cleanup.
- [Engine support](ENGINE_PARITY_MATRIX.md): tested fixture coverage across W0 and W1.
- [Known limits](KNOWN_LIMITS.md): supported boundaries and deferred language decisions.

## Runtime and libraries

- [C interoperability](FFI_VALIDATION.md): scalar ABI, opaque handles, and SQLite pilot.
- [Standard library](STDLIB.md): packages and their current contracts.
