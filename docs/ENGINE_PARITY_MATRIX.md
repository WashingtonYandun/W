# Engine Feature Parity Matrix & Implementation Boundaries

> **Milestone D01 Contract:** W explicitly documents the exact support status of each compiler engine across all language features. Releases do not claim universal parity while self-hosting limitations exist.

---

## 1. Compiler Engines & Architectural Roles

The W Language toolchain maintains four distinct execution targets, each with a defined architectural role:

```mermaid
flowchart TD
    subgraph W0 Reference Pipeline [W0 Reference Pipeline]
        SRC["W Source Code (*.w)"] --> P["Parser & Lexer"]
        P --> TC["TypeChecker & TypeInterner"]
        TC --> INTERP["1. W0 Interpreter (AST)"]
        TC --> HIR["HirBuilder & HirVerifier"]
        HIR --> HIR_C["2. W0 Typed HIR C99 (Default Backend)"]
        TC -.->|Diagnostic Oracle| AST_C["3. W0 AST C99 (Secondary Oracle)"]
    end

    subgraph W1 Self-Hosted Pipeline [W1 Self-Hosted Compiler]
        SRC2["W Source Code (*.w)"] --> W1_BIN["4. W1 Stage-2 Native Binary (Standalone)"]
        W1_BIN --> NATIVE_C["Emitted C99"]
    end
```

1. **W0 Interpreter (`runtime/Interpreter.py`):** Canonical reference AST tree-walking interpreter.
2. **W0 Typed HIR (`hir/HirCCodeGen.py`):** Primary production compiler backend (default since Milestone C06).
3. **W0 AST C99 (`codegen/CCodeGen.py`):** Secondary C99 oracle retained for differential fuzzing and cross-engine verification.
4. **W1 Self-Hosted (`selfhost/w1.w`):** Native Stage-2 standalone compiler binary compiled via 3-stage bootstrap fixed-point.

---

## 2. Feature Parity Matrix

The following table summarizes compiler support across the public core corpus. The counts are regenerated from `summary.json` by `tools/ci_conformance.py --matrix`, which reports measurements from the last verified run rather than restating `tests/engine_profiles.json`. Closures, FFI, generic OOP, stdlib and the LSP live in a separate expansion suite; see [EXPANSION.md](EXPANSION.md). Current project status and the next parity target are in [ROADMAP.md](ROADMAP.md).

<!-- GENERATED TABLE START -->

| Feature Category | Fixtures | W0 Interpreter | W0 AST C99 | W0 Typed HIR (Default) | W1 Self-Hosted C99 | Status / Milestone |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`core`** | 98 | ✅ 98/98 | ✅ 98/98 | ✅ 98/98 | ✅ 98/98 | Declared supported |
| **`generics`** | 15 | ✅ 15/15 | ✅ 15/15 | ✅ 15/15 | ⏳ 0/15 (15 declared unsupported) | Pending F01 |
| **`checked_modules`** | 1 | ✅ 1/1 | ✅ 1/1 | ✅ 1/1 | ⏳ 0/1 (1 declared unsupported) | Pending F01 |
| **Total Verified** | **114** | **114/114 (100.0%)** | **114/114 (100.0%)** | **114/114 (100.0%)** | **98/114 (86.0%)** | _measured_ |

Regenerate with `python3 tools/ci_conformance.py --matrix`, which reads `summary.json`
from an actual run of `python3 tools/ci_conformance.py` over the corpus. These are
measurements of the four engines, not a restatement of `tests/engine_profiles.json`;
`--matrix` reports `STALE` if the summary no longer covers the current corpus.

The `core` category includes five fixtures that pin runtime **panic** behaviour
(`panic_division`, `panic_modulo`, `panic_index`, `panic_dict_key`,
`panic_entrypoint_error`). Those declare the diagnostic they must raise with a
`# RUNTIME_PANIC: Wxxxx` marker instead of expected stdout, and every engine must report
that exact code and terminate non-zero. They exist because panic behaviour was the one
axis no fixture covered, which is how the interpreter and the two C backends were able to
disagree on it without any test noticing. `assignment_expression` covers the opposite
gap: a construct the checker accepted while the HIR backend rejected it.

<!-- GENERATED TABLE END -->

---

## 3. Detailed Feature Breakdown

### 3.1 Core Language & Control Flow (`core`)
- **Status:** **100% Parity** across all 4 engines.
- **Coverage:** 98 fixtures (positive runtime fixtures, control flow, functions, OOP contracts, recursion, and error diagnostics).
- **Features Included:**
  - Arithmetic, logic, bitwise, and comparison expressions.
  - While loops, range loops (`for i in 0..10`), break, continue, and scope cleanup.
  - If/elif/else expressions and statements.
  - Pattern matching (`match`) over primitives, tuples, and enums.
  - Native strings with byte-level length and UTF-8 iteration.
  - First-class tuple indexing and construction.

### 3.2 Value Semantics & Copy-on-Write (`core`)
- **Status:** **100% Parity** across all 4 engines.
- **Coverage:** Tested under `tests/runtime/list_cow.w`, `struct_cow.w`, `value_semantics_cow.w`, and `cow_telemetry.w`.
- **Features Included:**
  - Pure value semantics for `list[T]`, `dict[K, V]`, and user `struct` instances.
  - Path-copying detach asymptotics: $O(\text{shared path})$ complexity verified across all 4 engines.

### 3.3 Nominal OOP & Polymorphism (`core`)
- **Status:** **100% Parity** across all 4 engines.
- **Coverage:** Tested under `tests/runtime/oop_classes.w` and `examples/07_oop_polymorphism.w`.
- **Features Included:**
  - Single inheritance `class` hierarchies with `super` constructor calls.
  - Nominal `interface` contracts with explicit `implements`.
  - Dynamic method dispatch via vtables and `WVal` object wrappers.
  - Field encapsulation (`public` vs `private`).

### 3.4 Deterministic Memory & Weak References (`core`)
- **Status:** **100% Parity** across all 4 engines.
- **Coverage:** Tested under `tests/runtime/weak_references.w`, `memory_counters_verification.w`, and B03 leak suites.
- **Features Included:**
  - Deterministic `CleanupScope` ARC with zero tracing garbage collector pauses.
  - Control block architecture (`WWeakControl`) with separate strong and weak reference counters.
  - Safe `weak(obj)` handles and `upgrade(w)` returning `Option[T]`.
  - Verified under AddressSanitizer and LeakSanitizer: 0 memory leaks for acyclic and weak-broken structures.

### 3.5 Monomorphized Generics & ADTs (`generics`)
- **Status:** **Supported in W0** (15/15); **Unsupported in W1** (0/15).
- **Remediation Target:** **Milestone F01**.
- **Explanation:**
  - W0 supports generic functions `fn id[T]`, generic structs `struct Box[T]`, generic enums `enum Option[T]`, recursive ADTs (e.g. `enum Tree[T]`), and layout graph cycle checking (`W2011`).
  - W1's parser accepts enough syntax to produce a targeted error, but `selfhost/src/08_semantics.w` explicitly rejects generic function and record declarations with `W2013`.
  - Porting generic declaration collection, type substitution, specialization, layout-cycle checks and C lowering to W1 is the core objective of Milestone F01.

### 3.6 Checked Compilation Sessions & Modules (`checked_modules`)
- **Status:** **Supported in W0** (1/1); **Unsupported in W1** (0/1).
- **Remediation Target:** **Milestone F01**.
- **Explanation:**
  - W0 implements whole-program `CompilationSession` with arena deduplication and diamond import caching.
  - W1 has a source-level module expander in `selfhost/src/03_modules.w`: it loads imports, checks public names, qualifies module identities, and detects cycles before feeding a flattened token stream to the compiler.
  - This is not a W0-equivalent checked session. W1 does not share canonical typed declarations or specialization caches across module units. The current `checked_modules` fixture also requires imported generic specialization, which W1 rejects. F01 defines the measurable target: support the existing checked-module fixture while retaining the token-expansion frontend unless implementation evidence requires a larger redesign.

---

## 4. Bootstrap Fixed-Point vs. Core Corpus Parity

It is critical to distinguish between two distinct compiler guarantees:

1. **Bootstrap Fixed-Point (Deterministic Code Generation):**
   - The 3-stage bootstrap fixed-point ($\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$) proves that the self-hosted compiler `selfhost/w1.w` is self-consistent and emits bit-for-bit identical C99 code across successive generations when compiling itself.
   - It **does not** prove that W1 accepts all language constructs present in W0.

2. **Core Corpus Parity:**
   - Core corpus parity means every fixture in this 114-case public corpus passes on every engine, with no unsupported exclusions.
   - It does not claim W1 parity for the separate E expansion suite or every possible source program. F01 owns the 16 current W1 exclusions in this corpus.

---

## 5. CI Execution Profiles & Quality Gates

The compiler test harness (`tools/ci_conformance.py`) enforces strict behavioral quality gates:

### 5.1 Integration Profile (`--profile=integration`)
- Evaluates all 114 corpus fixtures across all engines.
- Skips unsupported features on specific engines based strictly on `tests/engine_profiles.json`.
- **Requirement:** Every unsupported feature must carry an explicit, non-empty tracking reason pointing to its roadmap milestone.
- **Result:** Passes (114/114) if and only if all supported features pass without failure, while accurately reporting unsupported counts.

### 5.2 Release Profile (`--profile=release`)
- Evaluates all 114 corpus fixtures across all engines without allowing any unsupported exclusions.
- **Requirement:** Every engine must pass 100% of all fixtures.
- **Result:** Intentionally fails as long as W1 has unsupported features (`generics`, `checked_modules`), preventing a release from claiming core-corpus parity before F01 is complete.

---

## 6. Standalone W1 Execution Contract

When invoking W1 via `w build --backend=selfhost <file.w>` or `w build --selfhost <file.w>`:
- The command executes the native `w1_stage2` binary directly via `subprocess.run([w1_bin, input, output])`.
- **No W0 pre-check or pre-filtering is performed.**
- If the source file contains features unsupported by W1 (such as generics), the native W1 compiler itself parses, validates, and emits its own error messages directly.
