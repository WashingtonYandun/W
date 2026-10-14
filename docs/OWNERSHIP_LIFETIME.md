# W Language Architecture: Deterministic Ownership & Lifetime Model (`v0.1.3`)

**Status:** Active Implementation Specification (`v0.1.3`)  
**Scope:** `W0 C99` (`codegen/CCodeGen.py`), `W1 C99` (`selfhost/w1.w`), and C99 Runtime (`runtime/w_runtime.h`)

---

## 1. Design Goals

W uses **deterministic single-threaded Reference Counting (RC) + Copy-on-Write (CoW)** without a tracing garbage collector and without exposing user-facing lifetime or borrow annotations.

In `v0.1.3`, the compiler enforces deterministic lifetime management across **all control-flow paths**:
1. Normal lexical block exit (`}`).
2. Early and final `return expr` statements (preserving returned values across cleanup).
3. Postfix error/optional propagation (`expr?`) on both `none` and `err` branches.
4. Loop exits (`break` and `continue`) across nested blocks down to the enclosing loop boundary.
5. Temporary expressions (`_tN`) created during left-to-right expression evaluation.
6. Reassignments (`x = expr`, `x[i] = expr`, `x.f = expr`), including self-assignments (`x = x`, `x = x[0]`).

---

## 2. Internal `ValueOwnership` Classification

Although W surface syntax has no ownership annotations, the C99 code generators (`W0` and `W1`) classify every C expression yielding a `WVal` into one of three internal ownership states:

```text
enum ValueOwnership {
    BORROWED      # Unowned view of an existing binding/parameter/field (e.g., local variable `x`, parameter `p`)
    OWNED         # Freshly allocated or retained WVal bound to a scope-tracked temporary `_tN` (refcount >= 1)
    TRANSFERRED   # Ownership moved out of a temporary (`w_move(&_tN)`) or newly cloned (`w_clone(expr)`) into a destination
}
```

### Ownership Transition Helper (`_own_expr`)
When a value is stored into a new variable (`let x = ...`), assigned (`x = ...`), or prepared for return (`return ...`):
- If the source expression is an `OWNED` temporary (`_tN`) registered in the current `CleanupScope`, the compiler emits **`w_move(&_tN)`** (`OWNED` $\rightarrow$ `TRANSFERRED`). `w_move` copies the `WVal` struct and overwrites `_tN` with `w_unit()` (`W_UNIT`), transferring the existing +1 reference count in $O(1)$ time with **zero redundant `retain`/`release` traffic**.
- If the source expression is a `BORROWED` reference (e.g., local variable `y`, parameter `p`), the compiler emits **`w_clone(y)`** (`BORROWED` $\rightarrow$ `TRANSFERRED`), incrementing `refcount` by +1 so the new binding owns an independent reference while `y` remains valid for its own scope cleanup.

---

## 3. `CleanupScope` Stack & LIFO Destruction Invariant

Both `W0` (`CCodeGen.py`) and `W1` (`selfhost/w1.w`) maintain an explicit lexical scope stack:

```text
struct CleanupScope {
    kind: str           # "fn" | "loop" | "block"
    vars: list[str]     # C WVal variable/temporary names declared in this scope
}
```

### 3.1 Registration Rules
- **Function Parameters:** Remain `BORROWED` for the duration of the call (owned by the caller's frame) and are **not** registered in the callee's `CleanupScope`. If a parameter is mutated in-place (or via `this`), CoW or object mutation operates on the target slot.
- **Local Bindings (`let x = ...`):** Initialized via `_own_expr(rhs)` and registered in the innermost `CleanupScope`.
- **Heap-Producing Temporaries (`_tN`):** Function calls, collection literals (`w_make_list`, `w_make_dict`, `w_make_tuple`), `struct` literals (`w_make_struct`), `class` instantiations (`w_new_Class`), string operations, and `w_unwrap_ok` are bound to `_tN` and immediately registered in the innermost `CleanupScope`.
  - *Note:* Auxiliary C initializer arrays use distinct prefixes (`_arrN`, `_kN`, `_vN`) so that `_tN` exclusively denotes scope-managed `WVal` temporaries.

### 3.2 Four Deterministic Exit Rules (LIFO Order)

1. **Normal Scope Exit (`}`):**
   When closing a C lexical block (`if`, `elif`, `else`, `while`, `for`, `match` arm, or function body), the top `CleanupScope` is popped and `w_release(v);` is emitted for each registered variable in **reverse declaration order (LIFO)**.

2. **`return expr` (Return Transfer Protocol):**
   To prevent releasing a local variable before returning it (e.g., `let x = [1, 2, 3]; return x`), `return` executes a 4-step protocol:
   ```c
   WVal _ret0 = w_clone(x);   /* or w_move(&_tN) if returning a temporary */
   /* Emit LIFO w_release(...) for ALL active scopes down to "fn" (without popping for subsequent unreachable code) */
   w_release(x);
   return _ret0;              /* or return w_ok(_ret0); in fallible T ! E functions */
   ```
   Because `_ret0` holds its own +1 reference (or moved reference from `_tN`), releasing `x` and all active temporaries in LIFO order safely decrements the scope's references while `_ret0` survives intact with `refcount >= 1`.

3. **Postfix Propagation (`expr?`):**
   Evaluating `expr?` binds the operand to a scope-tracked temporary `_t0 = _own_expr(op);`:
   - **On `W_NONE` (`T?` propagation):** Emits LIFO `w_release` across all active scopes down to `"fn"` (which includes `_t0` itself) and returns `w_none()`.
   - **On `W_ERR` (`T ! E` propagation):** Clones `_err = w_clone(_t0);`, emits LIFO `w_release` across all active scopes down to `"fn"`, and returns `_err`.
   - **On `W_OK` / non-`none`:** Extracts the payload (`_unw = w_unwrap_ok(_t0)` or `_t0`), registers `_unw` in the current `CleanupScope`, and continues execution.

4. **`break` and `continue` (Loop-Bounded Cleanup):**
   Emits LIFO `w_release` for every `CleanupScope` from the innermost scope outward **up to and including the nearest `"loop"` scope**, then emits `break;` or `continue;`. Variables in scopes enclosing the loop remain untouched.

---

## 4. Safe Reassignment & Slot Mutation (`w_assign` / `w_slot_assign`)

Reassigning a mutable local variable (`x = rhs`) or container/struct slot (`a[i] = rhs`, `s.f = rhs`) must release the old value stored in the destination while remaining safe under self-assignment (`x = x`, `x = x[0]`):
1. The right-hand side is evaluated and converted to an owned value **first** (`_own_expr(rhs)`).
2. `w_assign(&x, owned_rhs)` releases the previous value in `*dst` (`w_release(*dst)`) and writes `owned_rhs` into `*dst`.

---

## 5. Runtime RC Instrumentation & Leak Verification (`W_MEM_CHECK=1`)

In `runtime/w_runtime.h`, all heap-allocated runtime payloads (`WListBuf`, `WDictBuf`, `WTupleBuf`, `WStructBuf` for both `W_STRUCT` and `W_OBJECT`, and `WBoxBuf` for `W_OK`/`W_ERR`) carry an `int32_t refcount` header and participate in global telemetry counters:
- `w_g_alloc_count`: Total heap buffer allocations (`refcount = 1`).
- `w_g_free_count`: Total heap buffer deallocations when `refcount` reaches `0`.
- `w_g_retain_count`: Total `w_clone` increments on heap buffers.
- `w_g_release_count`: Total `w_release` decrements on heap buffers.
- `w_g_live_objects`: Currently live heap buffers (`w_g_alloc_count - w_g_free_count`).

### Safety Invariants
1. **Refcount Underflow / Double-Free Detection:** Both `w_clone` and `w_release` assert `refcount > 0`. Upon deallocation, `refcount` is poisoned to `-1` before `free()`. Any subsequent `w_clone` or `w_release` on a freed buffer immediately aborts with `[W4003] Runtime error: memory safety violation (refcount underflow / double free)`.
2. **Zero-Leak Exit Verification (`W_MEM_CHECK=1`):** At the end of `main()`, after releasing top-level and global bindings, `w_runtime_cleanup()` checks `getenv("W_MEM_CHECK")`. When set to `"1"`, if `w_g_live_objects != 0` or `w_g_alloc_count != w_g_free_count`, the process aborts with `[W4003]` and prints exact allocation/free/live counters.

---

## 6. Forward Compatibility with `v0.3` Typed HIR

The `CleanupScope` abstraction in `v0.1.3` is directly isomorphic to the explicit lifetime nodes planned for `v0.3` Typed HIR (`docs/HIR_ARCHITECTURE.md`):
- `CleanupScope` entry/exit $\leftrightarrow$ `HIRScope` + `HIRDrop(local_id)`
- `_own_expr` (`w_move` / `w_clone`) $\leftrightarrow$ `HIRMove` / `HIRRetain`
- `return` transfer + scope unwind $\leftrightarrow$ `HIRReturn`
- Postfix `?` unwind $\leftrightarrow$ `HIRPropagate`

## Phase A managed strings and constructor contracts

See ADR-006 for the current ownership extension. `w_str` borrows static storage; `w_owned_str` consumes a heap buffer and creates its RC owner; `w_copy_str` copies borrowed input such as argv. Dynamic strings participate in clone/release and allocation counters. `w_add` and `w_index_get_owned` results are registered owned temporaries in both native backends and W1. The borrowed `w_index_get` remains restricted to internal projection paths; dictionary value queries use the owned optional path.

`w_ok`, `w_err` and `w_enum_payload` consume their payload. Generated constructor calls move registered temporaries or clone borrowed arguments. `w_unwrap_optional`, `w_unwrap_ok`, `w_unwrap_err` and `w_unwrap_success` return owned values; peek helpers borrow. Class fields and collection slots own their stored values. Leak counters include string owners; LSan remains necessary to find allocations outside the instrumented ownership model.
