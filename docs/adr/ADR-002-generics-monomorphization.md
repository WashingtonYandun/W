# ADR-002: Generics & Monomorphization Strategy for W (`v0.2`)

- **Status:** Accepted (Target Implementation: `v0.2`)
- **Date:** 2026-10-13
- **Language:** W (`v0.1.2` Architecture Preparation)
- **Related Documents:**
  - [`SPEC.md`](../SPEC.md)
  - [`docs/HIR_DESIGN.md`](./HIR_DESIGN.md)
  - [`docs/TYPE_SYSTEM_DESIGN.md`](./TYPE_SYSTEM_DESIGN.md)

---

## 1. Context & Problem Statement

W `v0.1.x` supports parametric built-in collection and error/optional constructors (`list[T]`, `dict[K, V]`, `T?`, `T ! E`), user-defined value types (`struct`, `enum`), reference types (`class`, `interface`), a reference interpreter (`W0`), a C99 backend (`W0 C99`), and a self-hosted compiler (`W1` written in W).

However, user-defined types and functions cannot yet be parameterized over types (`struct Box[T]`, `fn id[T](x: T) -> T`). Introducing user-defined generics in `v0.2` requires choosing a compilation and runtime representation strategy that preserves W's core engineering invariants:

1. **Semantic Equivalence Across Engines:** `W0 Interpreter == W0 C99 == W1 C99`.
2. **Value vs. Reference Separation:** `struct`, `enum`, `list`, `dict`, and tuples have value semantics (recursive Copy-on-Write over acyclic graphs); `class` and `interface` have reference/identity semantics.
3. **Deterministic C99 Codegen & Self-Hosting Simplicity:** `W1` is compiled by itself in a 3-stage bootstrap fixed-point test (`w1_stage1.c == w1_stage2.c` SHA-256). The generics strategy must be straightforward to implement in W itself without requiring a complex JIT or runtime type-metadata VM.
4. **Native Optional & Result Primitives:** `T?` and `T ! E` are first-class primitives of the W type system and must not be duplicated by competing `Option[T]` / `Result[T, E]` standard library types.

---

## 2. Evaluated Options

### Option A: Compile-Time Monomorphization (Template Specialization)
Every reachable generic instantiation with concrete `TypeId` arguments (e.g., `Box[int]`, `Box[str]`, `id[int]`) is specialized during type checking / HIR lowering into a concrete declaration (`Box__int`, `Box__str`, `id__int`).

- **Pros:**
  - Zero new runtime representations needed in `w_runtime.h`: a specialized `struct Box__int` is a normal struct; a specialized `fn id__int` is a normal C function.
  - Preserves exact static types for C99 emission and field/method dispatch without additional indirection.
  - Simplifies `W1` self-hosting: once specialized in the AST/HIR, the existing C99 emitter handles concrete structs, enums, classes, and functions uniformly.
  - Value semantics and recursive CoW (`w_cow_clone`) work out of the box without needing runtime type descriptors.
- **Cons:**
  - Increases generated C99 code size proportional to the number of distinct concrete instantiations.
  - Requires cycle detection against infinite polymorphic recursion (e.g., `fn f[T](x: T) { f([x]) }`).

### Option B: Type Erasure (Uniform Boxed Representation)
Compile each generic declaration once operating over erased `WVal` values, inserting runtime casts or boxing/unboxing at boundaries (similar to Java generics).

- **Pros:**
  - Smaller generated C code size; single C function per generic W function.
- **Cons:**
  - Loses concrete type information needed for static method/field resolution on type parameters or value-type deep cloning unless runtime type descriptors (`TypeInfo*`) are passed implicitly.
  - Complicates C99 struct emission and `W1` codegen when generic structs/classes interact with interfaces and vtables.
  - Hides static specialization opportunities in numeric and struct-heavy workloads.

### Option C: Hybrid Dictionary Passing (Swift / Haskell Witness Tables)
Pass hidden runtime witness tables (`TypeMetadata` + protocol vtables) to generic functions while selectively specializing hot paths.

- **Pros:**
  - Supports separate compilation of generic libraries and dynamic polymorphism over unspecialized generics.
- **Cons:**
  - High implementation complexity for both `W0` and the self-hosted `W1` compiler.
  - Over-engineered for W's whole-program C99 compilation model.

---

## 3. Decision

**We select Option A: Compile-Time Monomorphization** as the canonical implementation strategy for W `v0.2`.

### 3.1 Core Design Principles

1. **Concrete Specialization by Canonical `TypeId` Tuple:**
   - Every generic instantiation `Decl[T1, ..., Tn]` is keyed by `(decl_name, (TypeId(T1), ..., TypeId(Tn)))` in the `TypeInterner`.
   - Each unique concrete tuple produces exactly one specialized declaration with a deterministic mangled identifier:
     - `Box[int]` $\rightarrow$ `Box__int`
     - `Pair[int, list[str]]` $\rightarrow$ `Pair__int__list_str`
     - `id[Point]` $\rightarrow$ `id__Point`
2. **Deterministic Emission Order:**
   - Specialized declarations are emitted in topological dependency order (and lexicographical tie-breaking on mangled names) so that `W1` Stage 1 and Stage 2 produce byte-for-byte identical C99 output (`SHA-256` fixed-point invariant).
3. **Container Invariance:**
   - All generic type constructors (`list[T]`, `dict[K, V]`, `Box[T]`, `Cell[T]`) are **invariant** in their type parameters (`SPEC.md` Section 4.1).
   - Even if `Dog <: Animal`, `list[Dog]` is **not** a subtype of `list[Animal]`, and `Cell[Dog]` is **not** a subtype of `Cell[Animal]`. This prevents unsound aliasing and mutation across reference and CoW containers.
4. **Preservation of Built-in `T?` and `T ! E`:**
   - `T?` (`OptionalType`) and `T ! E` (`ResultType`) remain built-in type system constructors with dedicated syntax (`?.`, `??`, `try`, `catch`, `ok(...)`, `err(...)`).
   - W `v0.2` will **not** introduce duplicate `Option[T]` or `Result[T, E]` types in the standard library. User-defined generic enums (e.g., `enum Tree[T]`) are used for domain-specific Algebraic Data Types.
5. **Polymorphic Recursion Limit:**
   - Monomorphization tracks instantiation depth per generic declaration and raises diagnostic `W2001` if a cyclic unguarded instantiation chain exceeds the maximum depth (default `64`).

---

## 4. Staged Implementation Plan for `v0.2`

To keep `W0` and `W1` synchronized and avoid large unverified diffs, `v0.2` will be implemented in four incremental milestones:

| Milestone | Scope | Key Deliverables |
|---|---|---|
| **`v0.2-alpha1`** | Generic `struct` | `struct Box[T]`, `struct Pair[A, B]`, explicit & inferred field initialization, value equality, recursive CoW |
| **`v0.2-alpha2`** | Generic `fn` & methods | `fn id[T](x: T) -> T`, call-site type argument inference + explicit `id[int](42)`, methods on `struct Box[T]` |
| **`v0.2-alpha3`** | Generic `enum` | `enum Tree[T]`, exhaustive `match` with specialized variant payloads |
| **`v0.2-alpha4`** | Generic `class` & `interface` | `class Cell[T]`, `interface Comparable[T]`, specialized vtable wiring |

Every milestone must pass:
- Conformance suite (`./w test`)
- 3-stage self-hosting fixed-point (`w1_stage1.c == w1_stage2.c`)
- Differential oracle (`./w test --differential`)
- Stress fuzzer (`./w test --fuzz`)
