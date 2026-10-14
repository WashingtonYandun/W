# ADR-005: Generic Hardening, Structural Growth Cycle Detection, and Code Bloat Telemetry

## Status
Accepted (v0.2.1)

---

## Context
Following the implementation of generic monomorphization (v0.2.0 Phase 1 & 2), the compiler confronted key scaling and safety considerations:
1. **Unbounded Template Expansions**: While a hard recursion limit (`MAX_DEPTH = 64`) caught infinite cycles, unbounded structurally growing instantiations (such as `Foo[T] -> Foo[list[T]]` or `fn expand[T](x: T) { expand([x]) }`) wasted compile cycles and produced late diagnostic errors at depth 64 rather than diagnosing the structural root cause at depth 1.
2. **Infinite Value Layouts**: Value-typed structs cannot contain themselves directly by value (`sizeof(Node) = sizeof(Node) + ...`), requiring static compile-time rejection with code `W2011`.
3. **Indirect Recursive ADTs vs False-Positive Cycles**: Indirected recursive structures (such as `enum Tree[T] { Node(Box[Tree[T]], Box[Tree[T]]) }`) require accessing the partially monomorphized parent type (`Tree[int]`) during the specialization of child containers (`Box[Tree[int]]`). Checking recursion stacks before checking the monomorphization cache caused false-positive cycle errors on valid recursive ADTs.
4. **Code Bloat & Canonical Keys**: Template specializations must never use strings as the source of truth for identity, and code bloat metrics (generated C lines, specialized symbols, deduplicated hits) must be tracked systematically.

---

## Decisions

### 1. Canonical Monomorphization Cache Key (`GenericInstanceKey`)
- Monomorphization identity is strictly grounded in canonical interner integer identifiers (`TypeId`), never formatted or mangled strings:
  ```python
  class GenericInstanceKey:
      template_name: str
      type_ids: Tuple[int, ...]
  ```
- Implements custom deterministic `__hash__` and `__eq__` methods ensuring $O(1)$ dictionary lookups without string allocation overhead.

### 2. Structural Growth Cycle Detection (`_type_complexity`)
- The compiler computes a structural complexity metric for concrete type arguments:
  $$\text{complexity}(T) = 1 + \sum_{C \in \text{children}(T)} \text{complexity}(C)$$
  where compound types (`list`, `dict`, `optional`, `result`, `tuple`, `fn`, `struct`, `enum`) recursively accumulate their constituent types.
- During monomorphization, if a template appears in the current instantiation stack with an increasing complexity metric ($C_{\text{current}} > C_{\text{previous}}$), the compiler rejects the expansion immediately with diagnostic `W2011` at step 1:
  > `[W2011] Structurally growing generic instantiation cycle detected for function 'expand' (complexity 1 -> 2)`

### 3. Cache-First Resolution Order for Indirect Recursive ADTs
- In `_monomorphize_struct`, `_monomorphize_fn`, and `_monomorphize_enum`, the compiler checks for cache hits (`key in self.monomorphized_...`) **before** inspecting the active instantiation stack.
- During the specialization of an indirect recursive ADT (`Tree[int]`), the type shell is registered in `monomorphized_enums` prior to child variant substitution. When `Box[Tree[int]]` resolves its field `val: Tree[int]`, it hits the cache immediately, returning the valid type shell and preventing false-positive cycle rejections.

### 4. Direct Recursive Layout Rejection
- Struct fields declaring the enclosing struct directly by value without indirection (`class` or `Box`) are rejected with `W2011`:
  > `[W2011] Recursive generic struct cycle detected for 'Node' without indirection`
- Enum variant payloads declaring the enclosing enum directly by value are rejected with `T025`:
  > `[T025] Recursive ADT variant 'Node' contains 'Tree' directly without indirection; use 'Box[...]'`

### 5. Telemetry & Code Bloat Metrics CLI (`--stats` / `--metrics`)
- The compiler integrates `MonomorphizationTelemetry` and `CodegenTelemetry`:
  - `specialization_requests`: Total generic monomorphization attempts.
  - `deduplicated_hits`: Number of requests satisfied by the canonical cache.
  - `specialized_structs`, `specialized_enums`, `specialized_functions`: Count of concrete emitted declarations.
  - `generated_c_lines`, `generated_c_bytes`: Exact volume of emitted C99 code.
- Exposed via CLI `--stats` / `--metrics` returning structured JSON for profiling and CI regression tracking.

---

## Consequences & Guarantees
- **Termination Guarantee**: Both direct and structurally growing generic instantiation cycles terminate at compile time in $O(1)$ expansion steps.
- **Valid Recursive ADTs Supported**: Algebraic tree and linked structures with explicit indirection compile cleanly into finite C99 tagged unions.
- **Zero Redundant Specialization**: Identical generic type arguments across different compilation units or functions reuse existing monomorphized definitions byte-for-byte.
- **Observable Code Generation**: Downstream users and CI pipelines can track code expansion and binary growth deterministically.
