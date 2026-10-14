# Types & Semantics (`[W-SPEC-TYPE]`)

## 1. Optional Types & Canonical Option ADT
- **`[W-SPEC-TYPE-010]` Canonical Equivalence**: The type syntax `T?` is strictly synonymous with `Option[T]`. The compiler canonicalizes all occurrences of `T?` to `Option[T]`.
- **`[W-SPEC-TYPE-011]` Option Variants**: `Option[T]` is an algebraic data type with two variants:
  - `Some(T)`: Carries the unwrapped value of type `T`.
  - `None`: Represents the absence of a value. The keyword `none` is semantic sugar for `Option.None`.
- **`[W-SPEC-TYPE-012]` Unwrapping & Propagation Operator**: The postfix operator `?` applied to an expression of type `Option[T]` evaluates to `T` if the value is `Some(val)`. If the value is `None`, it triggers an early return of `None` from the current function (which must return `Option[U]` or `U?`).

## 2. Fallible Types & Canonical Result ADT
- **`[W-SPEC-TYPE-020]` Canonical Equivalence**: The fallible type syntax `T ! E` is strictly synonymous with `Result[T, E]`.
- **`[W-SPEC-TYPE-021]` Result Variants**: `Result[T, E]` is an algebraic data type with two variants:
  - `Ok(T)`: Carries the successful result of type `T`.
  - `Err(E)`: Carries the error payload of type `E`.
- **`[W-SPEC-TYPE-022]` Result Propagation Operator**: The postfix operator `?` applied to an expression of type `Result[T, E]` evaluates to `T` if the value is `Ok(val)`. If the value is `Err(err)`, it triggers an early return of `Err(err)` from the current function (which must return `Result[U, E]` or `U ! E`).

## 3. Generic Types & Invariance
- **`[W-SPEC-TYPE-030]` Invariant Subtyping**: All generic type instantiations are strictly invariant. For any distinct types `A` and `B` where `A` is a subtype of `B`, `Container[A]` is neither a subtype nor a supertype of `Container[B]`. Assigning `Container[A]` to `Container[B]` raises a type error.
