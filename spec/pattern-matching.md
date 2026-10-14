# Pattern Matching & Algebraic Data Types (`[W-SPEC-PAT]`)

## 1. Pattern Destructuring on Algebraic Enums
- **`[W-SPEC-PAT-001]` Variant Patterns**: A match arm may match against an enum variant using `EnumName.Variant` or unqualified `Variant` when in scope.
- **`[W-SPEC-PAT-002]` Payload Destructuring**: If a variant carries a payload `Variant(T1, T2)`, the pattern `Variant(p1, p2)` binds variables `p1`, `p2` to the payload values within the arm's block.
- **`[W-SPEC-PAT-003]` Option Matching**: `Option[T]` (and `T?`) supports matching against `Some(binding)` and `None`:
  ```w
  match opt {
      Some(val) => print(val),
      None => print("absent")
  }
  ```
- **`[W-SPEC-PAT-004]` Result Matching**: `Result[T, E]` (and `T ! E`) supports matching against `Ok(val)` and `Err(err)`:
  ```w
  match res {
      Ok(val) => print(val),
      Err(err) => print(err)
  }
  ```

## 2. Exhaustiveness
- **`[W-SPEC-PAT-010]` Exhaustive Coverage**: Every `match` statement/expression over an enum must exhaustively cover all defined variants, or include a fallback wildcard `_` pattern. Unhandled variants trigger compile-time error `T030`.
