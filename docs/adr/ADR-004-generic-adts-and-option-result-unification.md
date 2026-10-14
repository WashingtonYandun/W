# ADR-004: Generic Algebraic Data Types (ADTs), Optional and Error Representation Unification

## Context
In W v0.1, fallible operations (`T ! E`) and optionality (`T?`) were introduced as specialized syntactic and semantic constructs. In v0.2.0 Phase 1, generic structs and functions with compile-time monomorphization were landed.
Advancing to Phase 2 (Generic Enums / Algebraic Data Types) creates a major semantic fork: introducing `enum Option[T]` and `enum Result[T, E]` as independent nominal types would create duplicate, parallel representations for the same concepts (`T?` vs `Option[T]`, `T ! E` vs `Result[T, E]`).
Furthermore, supporting recursive ADTs (e.g. `Tree[T]`) requires formalizing layout and indirection rules to prevent infinite stack layouts in C99, as well as clarifying constraint semantics and instantiation caching.

---

## Decisions

### 1. Canonical Unification: `T?` $\equiv$ `Option[T]`
- `T?` is defined as first-class canonical syntax sugar for the generic enum `Option[T]`.
- Canonical variants:
  - `Option.Some(T)` or unqualified `Some(T)`
  - `Option.None` or unqualified `None` (and keyword `none`)
- Semantic equivalence:
  - A variable declared as `let x: int? = 42` is identical to `let x: Option[int] = Some(42)`.
  - A variable assigned `none` is identical to `None`.
  - Pattern matching works uniformly:
    ```w
    match opt {
        Some(val) => print(val),
        None => print("empty")
    }
    ```
  - Operator `?` unwraps `Some(val)` or performs early-return of `None` if the enclosing function returns `Option[U]` or `U?`.

### 2. Canonical Unification: `T ! E` $\equiv$ `Result[T, E]`
- `T ! E` is defined as first-class canonical syntax sugar for the generic enum `Result[T, E]`.
- Canonical variants:
  - `Result.Ok(T)` or unqualified `Ok(T)`
  - `Result.Err(E)` or unqualified `Err(E)`
- Semantic equivalence:
  - A function signature `fn read() -> str ! IoError` is identical to `fn read() -> Result[str, IoError]`.
  - Return statements can use `return Ok(data)` or `return Err(error)`.
  - Pattern matching works uniformly:
    ```w
    match res {
        Ok(data) => process(data),
        Err(err) => log(err)
    }
    ```
  - Operator `?` unwraps `Ok(data)` or performs early-return of `Err(err)` if the enclosing function returns `Result[U, E]` or `U ! E`.
  - Non-ambiguity on nested types: `(int?) ! IoError` is `Result[Option[int], IoError]`. The outer `?` propagates `IoError`, yielding `Option[int]`. A second `?` propagates `None`.

### 3. C99 & Typed HIR Representation
- Monomorphized generic ADTs are lowered as standard C99 tagged unions:
  ```c
  typedef enum {
      Option__int_Tag_None = 0,
      Option__int_Tag_Some = 1
  } Option__int_Tag;

  typedef struct {
      Option__int_Tag tag;
      union {
          int64_t Some;
      } payload;
  } Option__int;
  ```
- Memory & ARC:
  - If a payload contains an ARC-managed reference (`str`, `list`, `class`, `dict`), the destructor/cleanup of the enum dispatches based on `tag` to release only the active variant.
  - Value semantics and Copy-on-Write (CoW) are preserved across tagged union assignments.

### 4. Recursive ADTs and Layout Rules
- **No Infinite Direct Layouts:** An enum variant or struct field cannot contain itself directly by value (`sizeof(T) = sizeof(T) + ...`). The TypeChecker strictly rejects unindirected self-containment with error `T025`.
- **Explicit Indirection via `Box[T]`:**
  - Recursive variants must use explicit heap boxing or references (`Box[T]` or `class` reference):
    ```w
    struct Box[T] {
        val: T
    }

    enum Tree[T] {
        Leaf(T),
        Node(Box[Tree[T]], Box[Tree[T]])
    }
    ```
  - This avoids implicit hidden magic while making memory cost explicit to the programmer.

### 5. Strict Nominal Constraints
- Interface constraints on type parameters (`[T: Printable]`) are **strictly nominal**.
- A type satisfies `[T: Printable]` if and only if it explicitly declares `implements Printable` (for classes) or provides a nominal implementation binding. Structural "duck typing" is rejected at compile time.

### 6. Instantiation Cache & Recursion Detection
- **Cache Key:** Monomorphization cache keys are strictly tuple-based: `(TemplateDeclId, Tuple[TypeId, ...])`, avoiding string-based truth sources.
- **Structural Growth Detection:** Beyond a hard `MAX_DEPTH = 64` failsafe, the TypeChecker detects structurally expanding instantiation chains (e.g. `Foo[T] -> Foo[list[T]] -> Foo[list[list[T]]]`) and aborts before hitting depth limits.
- **Code Bloat Tracking:** Metrics for `generic_instantiations`, `generated_C_lines`, and `deduplicated_instantiations` are integrated into compiler statistics.
