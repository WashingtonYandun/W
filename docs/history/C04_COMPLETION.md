# Milestone C04: Layout Graph, Finite Size Verification, and Recursive ADTs

## Executive Summary
Milestone C04 elevates W Language's type system from heuristic cycle checks to a formal **Layout Graph** with **Tarjan's Strongly Connected Components (SCC)** analysis on inline types, fully enabling first-class **Recursive Algebraic Data Types (ADTs)** such as generic binary trees and linked lists without artificial `Box[T]` wrappers.

---

## 1. Architectural Reasoning & Foundation

### 1.1 The Limitation Before C04
Previously, the W compiler relied on an artificial name-based heuristic (`pt.name == template.name` raising `T025`) that rejected any enum variant referencing the enum itself unless wrapped in an external struct that happened not to share the enum's name (e.g. `struct Box[T] { val: T }`). 
In reality, the W C99 runtime already boxes enum variant payloads on the heap (`WBoxBuf*`), meaning enum variant payloads are inherently **indirect reference edges** in memory layout. The artificial restriction prevented standard functional programming patterns like:
```w
enum Tree[T] {
    Leaf(T),
    Node(Tree[T], Tree[T])
}
```

### 1.2 The Formal Layout Graph
Milestone C04 replaces ad-hoc checks with `checker/LayoutGraph.py`:
- **EdgeKind.INLINE**: Direct value embedding where memory size is computed strictly by value composition (e.g. struct embedding another struct, tuples embedding structs).
- **EdgeKind.INDIRECT**: Indirection through heap buffers or references (enum variant payloads boxed via `WBoxBuf*`, class heap references, `Option` / `Result`, `Weak[T]`, dynamic list/dict buffers).

---

## 2. Cycle Detection with Tarjan's SCC

### 2.1 Theoretical Invariant
A composite type has an **infinite memory layout** if and only if there exists a directed cycle composed **exclusively of `INLINE` edges**:
$$\exists C = (v_1, v_2, \dots, v_k, v_1) \quad \text{such that} \quad \forall e \in C, \, \text{kind}(e) = \text{INLINE}$$

If any edge in the cycle is `INDIRECT`, the size of the referencing structure in memory is finite and statically fixed:
- A pointer/box in C99 is fixed (8 bytes on 64-bit systems).
- An enum tagged value (`WVal`) is fixed (24 bytes).

### 2.2 Algorithm & Diagnostics
`LayoutGraph.find_inline_sccs()` runs Tarjan's SCC algorithm restricted to the inline edge subgraph:
1. Identifies all strongly connected components where $|SCC| > 1$ or a single node with a self-loop.
2. Extracts an elementary directed cycle path (e.g. `CycleA -> CycleB -> CycleA`).
3. Emits diagnostic `[W2011]` pointing to the exact declaration line and column:
   ```
   [W2011] file.w:4:5 - Recursive generic struct cycle detected for 'CycleA' without indirection: cycle CycleA -> CycleB -> CycleA has only inline edges without reference indirection
   ```

---

## 3. Recursive ADTs & Runtime Memory Safety

### 3.1 First-Class Recursive Enums
Recursive enums (both generic and non-generic) are now first-class citizens in W:
```w
enum Tree[T] {
    Leaf(T),
    Node(Tree[T], Tree[T])
}

enum List[T] {
    Nil,
    Cons(T, List[T])
}
```

### 3.2 Type Interner Metadata
`checker/TypeInterner.py` was enhanced to preserve variant payload TypeIds:
- `EnumDef.variant_payloads: Dict[str, List[int]]` records the payload signature for every variant.
- `mk_enum` and `from_wtype` maintain canonical IDs without entering infinite recursion during self-referential type interning.

### 3.3 Active-Variant Destruction & Zero Leaks
When an enum instance with a payload is released (`w_release` in `runtime/w_runtime.h`):
1. Decrements the reference count of the payload box `bx = v.as.en.box`.
2. Upon reaching zero, invokes `w_release(bx->val)`.
3. If `bx->val` is a tuple (multiple payload arguments), it releases each element in the tuple recursively.
4. Frees `bx` and tracks the deallocation event in `w_mem_on_free()`.
Verified under AddressSanitizer and LeakSanitizer: recursive structures construct, clone, and tear down with **0 memory leaks**.

---

## 4. Pattern Matching with Guards & Exhaustiveness

### 4.1 Exhaustiveness Invariant
Match guards (`if condition`) introduce runtime dynamism and do **not** contribute to unconditional exhaustiveness.
If an enum pattern has a guard:
```w
match s {
    Status.Active(val) if val > 10 => val * 2,
    Status.Inactive => 0
    // Missing unconditional Status.Active(val) arm!
}
```
The compiler specializes the pattern matrix excluding guarded arms and raises `[W2003]` if any case is uncovered.

### 4.2 Codegen Semantics
In both `codegen/CCodeGen.py` and `hir/HirCCodeGen.py`:
- Guarded arms evaluate the condition within the arm's bound scope.
- If the guard evaluates to `false`, control falls through to subsequent match arms cleanly.
- `w_builtin_name` general matching matches monomorphized variants against the base generic enum template.

---

## 5. Verification & Test Suite

The dedicated test suite `test_c04_adt_layout.py` covers:
1. **Layout Graph Subgraph Isolation**: Proves Tarjan SCC isolates `INLINE` edges from `INDIRECT` edges.
2. **Infinite Layout Cycle Rejection**: Verifies `W2011` on self-cycles, mutual struct cycles, and inline tuple cycles.
3. **TypeInterner Metadata**: Validates `variant_payloads` retention in canonical `EnumDef`.
4. **Pattern Match Guards**: Verifies compile-time `W2003` enforcement on missing unconditional cases.
5. **Native C99 Execution**: End-to-end execution of recursive binary trees, recursive linked lists, and non-generic enums across AST and HIR backends under AddressSanitizer.

**Conformance Result:**
- **397 / 397 tests passing (100%)**
- **101 / 101 tests passing under AddressSanitizer / UndefinedBehaviorSanitizer (100%)**
