# W Language Architecture: Deterministic Ownership & Lifetime Model (`v0.1.3`)

**Status:** Implemented & Verified Specification (`B01-B04`, `D01-D06` / `ADR-009`)  
**Scope:** `W0 Typed HIR` (default), `W0 AST C99` (oracle), `W1 C99` (`selfhost/w1.w`), and C99 Runtime (`runtime/w_runtime.h`)

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

## B01: runtime helper inventory and evaluation contract

The following contracts supersede older blanket claims in this document. Ownership
is an emitter convention, not a dedicated HIR ownership type or a formal proof.
A borrowed argument stays valid for the whole helper call. An owned result carries
one release obligation, including when it happens to be an immediate scalar.

### Helpers that consume ownership

- `w_release` and `w_release_array` consume one reference per value/array element.
- `w_move` transfers the slot's ownership and resets it to unit.
- `w_assign` consumes its owned source, releases the old destination, stores the
  source, and returns a **borrowed** view of that destination. The caller must
  protect a self-aliasing source before calling it.
- `w_ok`, `w_err`, `w_enum_payload` consume their payload; `w_wrap_result` consumes
  its input and returns it or a new success wrapper. They do not clone payloads.
- `w_owned_str` consumes a malloc buffer; `w_copy_str` borrows bytes and copies them.

### Borrowed input, owned output

- `w_clone` retains managed storage. Immediate values and borrowed static strings
  require no retain, and release is a no-op for them.
- `w_unwrap_optional`, `w_unwrap_ok`, `w_unwrap_err`, `w_unwrap_success` retain their
  returned payload; the source wrapper may be released independently.
- `w_index_get_owned` and `w_dict_get` retain their result. Present dictionary
  values are wrapped, including present None. String indexing allocates a string.
- `w_make_list`, `w_make_tuple`, `w_make_dict`, `w_make_struct`, `w_make_object`
  borrow their initializer arrays and clone the stored values. `w_make_range`
  creates an owned list. Field/variant/type names come from static generated C.
- `w_dict_keys`, `w_dict_values`, `w_builtin_bytes`, `w_builtin_enumerate`,
  `w_builtin_dict_items` create owned containers and retain contained values.
- `w_add` borrows operands; string addition returns owned storage. Numeric results
  from add/sub/mul/div/mod/neg/lt/le/gt/ge are immediate values.
- `w_builtin_str`, `w_builtin_chr`, `w_builtin_slice` return owned strings.
  `str(existing_string)` retains its buffer. `w_builtin_read_file` and
  `w_builtin_write_file` return owned results, including owned error payloads.
- `w_builtin_args` returns an owned list of copied strings; `w_init_args` only
  borrows process argv until copying. `w_to_cstr` returns malloc storage requiring
  `free`, not `w_release`; print/eprint and string conversion consume that buffer.

### Short-lived borrows and mutable slots

- `w_peek_optional`, `w_peek_ok`, `w_peek_err`, `w_member_get` return borrowed
  payloads. Keep the owner alive and unchanged until cloning/consuming the borrow.
- Legacy `w_index_get` borrows list/dict elements but owns a string-index result.
  Generated value reads use `w_index_get_owned`; W1 retains the legacy expression
  only as lvalue metadata, without executing a discarded value read.
- `w_index_ref` and `w_member_ref` borrow the root slot, may detach value storage,
  and return a mutable slot pointer. Indices are evaluated once into stable values.
  Slot pointers cannot be cached across unrelated mutations of their container.
- `w_list_append` borrows the item and clones it into the destination, detaching
  as needed. `w_list_pop` transfers the removed element's ownership to its caller.
  `w_list_clear` releases removed elements. All three borrow the destination slot.
- `w_list_detach`, `w_dict_detach`, `w_struct_detach` replace the borrowed slot's
  buffer and clone shared children; callers retain ownership of the root slot.
- `w_unit`, `w_none`, `w_int`, `w_float`, `w_bool`, `w_enum` produce immediate or
  payload-free values. `w_str` borrows static bytes. `w_eq`, `w_is_none`,
  `w_builtin_name`, UTF-8 helpers, len/int/float/ord borrow inputs and return
  scalars. Print/eprint borrow arguments and return unit.

### Generated calls, evaluation and exits

Function/method arguments and `this` are borrowed from the caller, which retains
snapshots through the call. Parameters are immutable bindings; class identity
remains shared. Callees return owned values. Dispatchers forward that contract;
constructors return owned objects and clone stored fields.

Before evaluating later operands, emitters materialize earlier borrowed or lazy
values into registered temporaries. This covers arguments, binary left operands,
read receivers, collection entries and struct fields. Field reads retain their
value immediately. Collection initialization evaluates key then value per entry.
Already-owned temporaries are reused. These snapshots can increase RC/CoW traffic;
B02 must measure that cost before optimizing lifetimes.

Assignments evaluate and protect the RHS before evaluating the target, following
the interpreter contract. The RHS hold is registered before any target computation
that can propagate; successful assignment moves it into the slot. W1 replays target
emission after RHS evaluation rather than emitting target effects prematurely.

Return and propagation protect the escaping value before LIFO cleanup. Break and
continue clean through the nearest loop; the for iterable belongs to its outer
scope. Lazy and/or/?? branches allocate and release only when executed. Empty
constructors and discarded ranges are registered just like nonempty constructors;
a fresh empty list stored directly into a global can transfer without a temporary.

### Reproducible acceptance

`python3 test_ownership_control_flow.py` compares the interpreter with AST C, HIR C
and standalone W1 emission. All three native binaries run under ASan/UBSan and
W_MEM_CHECK; Linux additionally enables LSan. The fixture covers retained fields
across later mutation, argument/collection order, local field/index returns,
temporary receivers, self-assignment, append of an existing element, nested loop
exits, optional/result propagation in match, failing assignment targets, handler
payloads, short-circuit effects, coalesce and discarded constructors.

Strong RC cycles remain unsupported (B03). Explicit process exit and runtime
panics terminate the process rather than unwinding lexical scopes; they are not
zero-leak acyclic success cases. Allocation failure and concurrent RC are outside
this contract. W1 generic-language exclusions remain unchanged; this fixture uses
its supported non-generic profile and unqualified Ok/Err constructors.

## B03: class control blocks and weak handles

Class ownership is recorded in a control block with strong and weak counts and a
nullable object pointer. One implicit weak reference protects the block while the
object is alive. `w_clone`/`w_release` update strong counts for objects and weak
counts for handles. At strong zero, invalidate the object pointer, release fields,
destroy object storage and drop the implicit weak reference. A self-stored weak
handle therefore cannot free its control block during object teardown.

`w_builtin_weak` borrows a class reference and returns one owned weak handle.
`w_builtin_weak_owned` consumes the evaluated language-call snapshot immediately,
so weak creation does not accidentally keep its target alive until scope cleanup.
`w_builtin_upgrade` borrows a weak handle and returns a retained strong object or
None. `w_empty_weak` owns a new expired control block for a default weak field;
constructor initializer arrays release their temporary defaults after storing
clones. Weak identity remains stable until the final handle is released.

Memory instrumentation counts control blocks as managed allocations. Class
objects therefore have separate object/body and control-block obligations. CoW
byte accounting uses the current ABI and includes the changed struct header size.

`test_weak_references.py` isolates the unbroken strong cycle in `tests/memory/`:
its leak is expected only for that subprocess. Broken cycles and weak back-reference
cases must have zero leaks. Linux keeps LSan enabled and additionally requires its
leak report for the negative case; no suite-wide leak suppression is introduced.
The interpreter uses Python weak references and identity sentinels. Python GC may
collect strong cycles; native RC behavior is the authority for the cycle test.

The isolated Linux cycle negative sets LSAN_OPTIONS=use_stacks=0:use_registers=0
to ignore stale machine roots after create_cycle returns. Success cases retain
normal root scanning and leak detection. This changes conservative reachability
for the expected-leak process only; it does not suppress leaked allocations.

---

## 11. Phase D Memory Safety & Sanitizer Gate (ADR-009)

As formalized in `ADR-009-Consolidation-and-Parity-Contracts.md`:
1. **Continuous Sanitizer Matrix:** The full test suite runs under Clang AddressSanitizer (ASan), UndefinedBehaviorSanitizer (UBSan), and Linux LeakSanitizer (LSan) across 107 test fixtures on every pull request.
2. **Zero Unintended Leaks:** All acyclic data structures, CoW path-copying mutations, monomorphized generic containers, and weak-reference broken cycles must exhibit zero memory leaks.
3. **Deterministic Scope Cleanup:** The `CleanupScope` LIFO unwinding guarantees that memory is released immediately at scope exits across all four execution engines.

