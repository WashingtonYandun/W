# Generics & Monomorphization (`[W-SPEC-GEN]`)

## 1. Declarations & Instantiation
- **`[W-SPEC-GEN-001]` Monomorphization**: Generic structs, functions, and enums are template declarations. They emit concrete definitions only upon instantiation with concrete types.
- **`[W-SPEC-GEN-002]` Mangled Identifiers**: Specialized symbols follow deterministic naming:
  `TemplateName__T1__T2` where `T1`, `T2` are recursively mangled concrete type names.
- **`[W-SPEC-GEN-003]` Instantiation Caching**: The compiler caches monomorphized declarations using a canonical tuple key `GenericInstanceKey(TemplateDeclId, (TypeId, ...))`. Repeated references to the same specialization share identical C99 type definitions.
- **`[W-SPEC-GEN-004]` Structural Growth Cycle Detection**: Beyond a hard recursion depth limit (`MAX_DEPTH = 64`), the TypeChecker detects structurally expanding generic instantiations (where type nesting complexity monotonically grows: $C_{k+1} > C_k$) and aborts immediately with diagnostic code `W2011`.
- **`[W-SPEC-GEN-005]` Code Bloat Metrics & Telemetry**: The compiler tracks specialization requests, cache deduplication hits, and generated C lines/bytes, exposing them via CLI flag `--stats` / `--metrics`.

## 2. Layouts & Recursive ADTs
- **`[W-SPEC-GEN-010]` Finite Size Invariant**: Every struct and enum must have a statically determinable finite layout in C99.
- **`[W-SPEC-GEN-011]` Rejection of Infinite Direct Layouts**: An enum variant or struct field cannot directly contain an instance of itself by value without reference indirection. Direct self-containment triggers compile error `T025`.
- **`[W-SPEC-GEN-012]` Explicit Indirection**: Recursive algebraic structures must use an indirect pointer or heap box (e.g. `Box[T]` or a `class` reference) for recursive branches.

## 3. Constraints
- **`[W-SPEC-GEN-020]` Nominal Constraints**: Interface constraints `[T: InterfaceName]` are strictly nominal. A concrete type satisfies the constraint if and only if it explicitly declares that it implements the interface. Structural compatibility without nominal declaration is rejected at compile time.
