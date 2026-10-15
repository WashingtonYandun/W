# C03 Milestone Completion: Typed Generic Specialization on HIR & Structural Mangling

**Milestone:** C03 · P1 · Monomorfización tipada  
**Status:** Completed & 100% Conformance Verified (393/393 PASS)  
**Branch:** `feat/c03-generic-specialization-hir`  

---

## 1. Context & Architectural Motivation

In earlier versions of W Language, generic specializations were performed via recursive AST copying without a formal worklist state model, caching based solely on un-namespaced type names, and mangling names with naive `__` concatenation (e.g. `Box[int]` became `Box__int`). This created several structural vulnerabilities:
1. **Identifier Collisions:** A user-declared struct `struct Box__int` collided directly with specialized `struct Box[int]`.
2. **Fragile Recursion:** Mutual generic expansions or regular recursions could either cycle infinitely or prematurely abort without reporting the causal instantiation chain.
3. **Module & DeclId Blindness:** Generic templates across multiple modules with identical local names could collide or share invalid instances.
4. **Non-deterministic Emission:** Declaration ordering depended on Python dictionary iteration order, causing emitted C code to fluctuate across different `PYTHONHASHSEED` configurations.

Milestone **C03** resolves these foundational issues by implementing a formal worklist-driven specialization engine with explicit states, length-prefixed collision-free mangling, structural growth cycle detection with diagnostic chains, and deterministic topological ordering.

---

## 2. Core Technical Implementations

### 2.1 Immutable Specialization Keys & State Machine
- **`GenericInstanceKey`**:
  Defined as an immutable `NamedTuple(template_name, type_ids, module_id=None, decl_id=None)`. Guarantees hash consistency and safe usage as dictionary keys.
- **`SpecializationState`**:
  Enum defining explicit lifecycle states:
  - `PENDING`: Instance requested and queued for monomorphization.
  - `SPECIALIZING`: Instance currently undergoing type-checking and body elaboration. Used for cache-first resolution of regular recursion.
  - `COMPLETE`: Fully verified specialization published and ready for code emission.
  - `FAILED`: Specialization failed during semantic checking; poison-pilled to prevent reuse.
- **`SpecializationEntry`**:
  Encapsulates key, state, `specialized_type`, `specialized_symbol`, `ast_decl`, and transitive specialization dependencies.

### 2.2 Collision-Free Structural Mangling Scheme
- **Scheme Definition:**
  ```text
  _W_G_{len(module)}_{module}__{len(template)}_{template}__{arg_mangles}
  ```
  - Example: `Box[int]` -> `_W_G_3_Box__int`
  - Example: `Pair[int, str]` -> `_W_G_4_Pair__int__str`
- **Separation from User Namespaces:**
  - Identifiers starting with `_W_` or `__w_` are reserved by the compiler and strictly rejected in user source with diagnostic code `W1002`.
  - User identifiers containing `__` (e.g., `Box__int`, `id__int`) remain in the user namespace and never collide with compiler-synthesized specializations.
- **Built-in ADT Compatibility:**
  - Built-in `Option` and `Result` types preserve canonical names (`Option__{args}`, `Result__{args}`) to maintain C runtime and interpreter ABI compatibility.

### 2.3 Structural Inductive Cycle Detection & Diagnostics
- Multi-step inductive complexity tracking ($T_0 \prec T_1 \prec T_2$) distinguishes:
  - **Regular recursion** (`countdown[T]` calling `countdown[T]`): Terminated cleanly via `SPECIALIZING` cache lookup.
  - **Finite ground jumps** (`fixed[T]` calling `fixed[list[int]]`): Terminated as closed ground types reaching a fixed point.
  - **Unbounded inductive expansions** (`expand[T]` calling `expand([T])`, or mutual expansion `a[T]` <-> `b([T])`): Aborted with diagnostic code `W2011`, formatting the exact instantiation stack trace into the error message.

### 2.4 Deterministic Topological Declaration Sorting
- Implemented `_sort_monomorphized_decls()` in `TypeChecker`:
  - Specialized structs are sorted using Kahn's topological sort based on structural field dependencies.
  - Specialized functions and enums are sorted canonically by mangled name.
  - Emitted C code is byte-identical across runs with different `PYTHONHASHSEED` (`0`, `42`, `12345`, `999999`).

---

## 3. Verification & Test Evidence

The dedicated test suite `test_c03_generic_specialization.py` verifies all six core invariants:
1. `test_collision_freedom`: Co-existence of user `Box__int` / `id__int` with generic `Box[int]` / `id[int]`.
2. `test_reserved_compiler_prefix`: Compile-time rejection of user declarations starting with `_W_` / `__w_` (`W1002`).
3. `test_regular_recursion_termination`: Termination and single-instance verification for recursive functions.
4. `test_structural_expansion_diagnostics`: Direct and mutual expansion cycle detection with chain diagnostics (`W2011`).
5. `test_deterministic_topological_sorting_and_hashseed`: Byte-identical C output across 4 distinct `PYTHONHASHSEED` values.
6. `test_native_c99_execution`: End-to-end compilation with AddressSanitizer and UndefinedBehaviorSanitizer across AST and HIR backends.

### Full Conformance Suite Results (`./w test`)
```text
C99 Native Backend:  47/47
HIR C99 Backend:     47/47
W1 Stage-2 Runtime:  38/38
W1 Modular Split:    1/1 (Loss-less verified)
Generic Hardening:   1/1 (Canonical cache verified)
CoW Telemetry (B02): 1/1 (Asymptotics verified)
Compilation Session: 1/1
Resolved HIR (C02):  1/1
Generic Specialization (C03): 1/1
Examples E2E Suite:  7/7
Bootstrap FixedPoint:1/1 (SHA256 verified)
==================================================
ALL 393/393 CONFORMANCE, EXAMPLES & SELF-HOSTING TESTS PASSED (100%).
```
