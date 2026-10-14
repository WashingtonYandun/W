# The W Programming Language

<p align="center">
  <a href="https://github.com/WashingtonYandun/W/actions"><img src="https://img.shields.io/badge/build-passing-brightgreen?style=flat-square" alt="Build Status"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/conformance-347%2F347%20(100%25)-success?style=flat-square" alt="Conformance Tests"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/sanitizers-ASan%20%7C%20UBSan%20clean-blue?style=flat-square" alt="Sanitizers"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/self--hosting-3--stage%20fixed--point-purple?style=flat-square" alt="Self-Hosting"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/version-v0.2.0--alpha-informational?style=flat-square" alt="Version"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/backend-portable%20C99-orange?style=flat-square" alt="Backend"></a>
  <a href="https://github.com/WashingtonYandun/W/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen?style=flat-square" alt="Contributions Welcome"></a>
  <a href="CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg?style=flat-square" alt="Code of Conduct"></a>
</p>

<p align="center">
  <strong>Compact &bull; Deterministic &bull; Statically Typed &bull; Self-Hostable Systems Language</strong><br>
  <em>Engineered with pure Value Semantics, Copy-on-Write (CoW), Deterministic ARC, Monomorphized Generics, Algebraic Data Types, and portable C99 compilation without Garbage Collection pauses.</em>
</p>

---

## ⚡ What is W?

**W** is a modern systems and application programming language combining the expressive safety of modern functional languages with the raw speed, minimal footprint, and portability of C99. W features a self-hosting compiler, deterministic memory management without a tracing garbage collector, monomorphized generics, first-class Algebraic Data Types (ADTs), and seamless nominal object-oriented programming.

### Key Architectural Pillars

| Pillar | How W Solves It | Technical & Operational Benefit |
| :--- | :--- | :--- |
| **Hybrid Memory Architecture** | Pure Value Semantics + Copy-on-Write (CoW) for data structures (`list`, `dict`, `struct`); Single-threaded ARC for OOP `class` objects | Zero garbage collector pauses; deterministic `CleanupScope` releases memory immediately at scope exit; ASan/UBSan clean. |
| **Semantic Unification (`Option` & `Result`)** | Formal equivalence: `T?` $\equiv$ `Option[T]` (`Some(T)`, `None`) and `T ! E` $\equiv$ `Result[T, E]` (`Ok(T)`, `Err(E)`) | Single mental model: use `?` and `??` for concise control flow or `match` for structural destructuring interchangeably. |
| **Monomorphized Generics & ADTs** | Compile-time specialization of generic `struct[T]`, `enum[T]`, and `fn[T]` with deterministic `TypeId` tuple mangling | Zero runtime dispatch overhead for generics; static detection of infinite recursive layouts (`T025`); nominal constraints (`[T: Printable]`). |
| **Nominal OOP & Polymorphism** | Single-inheritance `class` hierarchies, nominal `interface`, explicit `implements`, `super`, and field encapsulation (`public`/`private`) | Reliable enterprise software modeling with static vtable layout and dynamic method dispatch. |
| **Self-Hosting Fixed-Point** | 3-stage bootstrap fixed-point: $\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$ | Proof of linguistic maturity, deterministic code generation, and complete compiler autonomy. |
| **Typed HIR Multi-Pass Pipeline** | `Lexer` $\to$ `Parser` $\to$ `TypeInterner` $\to$ `Typed HIR` $\to$ `HirCCodeGen` $\to$ `C99` | Clean separation between semantic validation, generic monomorphization, intermediate representation, and target code generation. |
| **Ultra-Lightweight Footprint** | Standalone single-header runtime (`runtime/w_runtime.h`), zero external runtime dependencies | Generated binaries are $\approx 34\text{ KB}$, portable across Linux, macOS, BSD, and embedded targets. |

---

## 🚀 Quick Start & Installation

### Prerequisites
- **Python** $\ge 3.10$ (driver and reference compiler)
- **C99 Compiler** (`clang` or `gcc`)
- Zero external package dependencies.

### One-Line Install & Verification

```bash
git clone https://github.com/WashingtonYandun/W.git
cd W

# Compile Stage-2 native W1 compiler and install globally to ~/.local/bin/w
./install.sh

# Verify installation & run the 347-test conformance matrix
w version
w test
```

---

## 💻 Language Tour

### 1. Monomorphized Generics & Algebraic Data Types (ADTs)

W provides full parametric polymorphism with monomorphization and recursive data structure protection:

```w
# Generic Struct
struct Box[T] {
    val: T
}

# Recursive Algebraic Data Type (explicit heap indirection via Box[T])
enum Tree[T] {
    Leaf(T),
    Node(Box[Tree[T]], Box[Tree[T]])
}

fn sum_tree(t: Tree[int]) -> int {
    return match t {
        Leaf(v) => v,
        Node(l, r) => sum_tree(l.val) + sum_tree(r.val)
    }
}

let left = Tree.Leaf(10)
let right = Tree.Leaf(20)
let root = Tree.Node(Box(left), Box(right))

print("Tree sum:", sum_tree(root)) # 30
```

### 2. Canonical Option & Result Unification

In W, `T?` is identical to `Option[T]`, and `T ! E` is identical to `Result[T, E]`:

```w
fn parse_id(raw: str) -> int ! str {
    if len(raw) == 0 {
        return Err("empty raw id")
    }
    return Ok(101)
}

fn fetch_user(id: int) -> str? {
    if id == 101 {
        return Some("Alice")
    }
    return None
}

fn process_request(raw_id: str) {
    # 1. Postfix error propagation with '?'
    let id: int = parse_id(raw_id)?

    # 2. Pattern matching over Option / Result
    match fetch_user(id) {
        Some(name) => print("User found:", name),
        None       => print("User not found")
    }
}
```

### 3. Pure Value Semantics + Copy-on-Write (CoW)

Collections and structs behave as mathematical values with zero unintended side effects:

```w
let original = [1, 2, 3]
let mut copy = original

# Mutating copy triggers transparent Copy-on-Write detachment
copy.append(4)

print(original) # [1, 2, 3] - completely untouched
print(copy)     # [1, 2, 3, 4]
```

### 4. Object-Oriented Contracts & Nominal Constraints

```w
interface Printable {
    fn to_string() -> str
}

class User implements Printable {
    private name: str
    private age: int

    fn init(name: str, age: int) {
        this.name = name
        this.age = age
    }

    public fn to_string() -> str {
        return this.name + " (" + str(this.age) + ")"
    }
}

# Strictly nominal constraint: T must explicitly declare 'implements Printable'
fn print_item[T: Printable](item: T) {
    print("Item:", item.to_string())
}

let user = new User("Washo", 28)
print_item(user)
```

---

## 🛠️ CLI Toolchain (`w`)

The `w` driver provides a unified interface for compilation, formatting, and analysis:

```bash
# 1. Execute via the W0 interpreter
w run examples/01_hello_world.w

# 2. Static type checking with machine-readable JSON diagnostics
w check examples/03_enums_and_match.w
w check examples/03_enums_and_match.w --json

# 3. Canonical code formatter (idempotent, standard style)
w fmt examples/01_hello_world.w --write

# 4. Transpile W to portable C99 via Typed HIR backend or self-hosted W1
w emit-c --hir examples/05_utf8_and_algorithms.w -o out.c
w emit-c --selfhost examples/05_utf8_and_algorithms.w -o out_w1.c

# 5. Compile directly to optimized native binary (~34 KB)
w build --hir examples/05_utf8_and_algorithms.w -o app
w build --selfhost examples/05_utf8_and_algorithms.w -o app_w1

# 6. Run full 347-test conformance suite (100% pass)
w test

# 7. Run AddressSanitizer & UndefinedBehaviorSanitizer checks
w test --sanitize

# 8. Run differential testing oracle & compiler fuzzer
w test --differential 50 --seed 20260416
w test --fuzz 2000 --seed 20260416

# 9. Performance benchmark harness
w bench
```

---

## 🏛️ Compiler Architecture

W follows a multi-pass pipeline designed for mathematical correctness, invariant preservation, and formal verification:

```text
Source Code (.w)
       │
       ▼
 ┌──────────┐
 │  Lexer   │  ──▶ 31 Keywords, UTF-8 codepoints, strict numeric literals
 └────┬─────┘
       ▼
 ┌──────────┐
 │  Parser  │  ──▶ Precedence parser, AST with source spans & error recovery
 └────┬─────┘
       ▼
 ┌───────────────┐
 │  TypeChecker  │ ──▶ Two-pass analysis, TypeInterner (TypeId), Nominal Subtyping
 └────┬──────────┘
       ▼
 ┌───────────────┐
 │   Typed HIR   │ ──▶ Canonical High-level Intermediate Representation
 └────┬──────────┘
       │
       ├──▶ Monomorphization (TypeId tuple canonical key, recursion limit guard)
       │
       ▼
 ┌───────────────┐
 │  HirCCodeGen  │ ──▶ Deterministic CleanupScope ARC, dynamic dispatch, CoW
 └────┬──────────┘
       ▼
  Portable C99 ──▶ Clang / GCC (-O2) ──▶ Standalone Native Binary (~34 KB)
```

### Self-Hosted Compiler Modules (`selfhost/src/`)
The self-hosted compiler is decomposed into 9 single-responsibility modules:
- `selfhost/src/01_ast.w`: AST node definitions, `ExprRes`, and `CleanupScope`.
- `selfhost/src/02_lexer.w`: Lexical scanner and keyword predicates.
- `selfhost/src/03_token_stream.w`: Lookahead and token assertions.
- `selfhost/src/04_emitter.w`: C99 emission and temporary register allocation.
- `selfhost/src/05_metadata.w`: Type tables, OOP class/interface vtables.
- `selfhost/src/06_parser_expr.w`: Precedence-based expression parser.
- `selfhost/src/07_parser_decl.w`: Top-level statement and type declaration parser.
- `selfhost/src/08_checker.w`: Semantic validation and stable error codes (`W0xxx`–`W4xxx`).
- `selfhost/src/09_main.w`: CLI driver and pipeline coordinator.

---

## 📊 Performance & Benchmarks

Run `./w bench` to benchmark the reference interpreter against the native C99 backends:

| Benchmark | W0 Interp (ms) | W0 C99 (ms) | W1 Native (ms) | Speedup vs Interp | Binary Size |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`arithmetic.w`** | 77.85 ms | 7.14 ms | 6.73 ms | **11.6x** | 34.3 KB |
| **`function_calls.w`** | 139.50 ms | 6.09 ms | 7.34 ms | **19.0x** | 34.4 KB |
| **`list_iteration.w`** | 63.27 ms | 7.47 ms | 7.50 ms | **8.4x** | 34.4 KB |
| **`list_copy.w`** (CoW) | 72.36 ms | 10.06 ms | 7.10 ms | **10.2x** | 34.6 KB |
| **`nested_cow.w`** (Path Copying) | 50.21 ms | 7.73 ms | 3.44 ms | **14.6x** | 34.8 KB |
| **`structs.w`** | 90.17 ms | 8.62 ms | 7.25 ms | **12.4x** | 34.5 KB |
| **`objects.w`** (OOP ARC) | 74.98 ms | 7.17 ms | 6.89 ms | **10.9x** | 34.5 KB |
| **`dynamic_dispatch.w`** | 97.57 ms | 7.76 ms | 6.39 ms | **15.3x** | 34.5 KB |

---

## 🗺️ Roadmap & Language Evolution

- [x] **v0.1.0** — Core language, OOP (`class` & `interface`), C99 backend, 3-stage self-hosting fixed-point.
- [x] **v0.1.1** — Semantic hardening, recursive nested CoW, constructor desugaring, 3-engine differential oracle.
- [x] **v0.1.2** — Stable diagnostic codes (`W0xxx`–`W4xxx`), fuzzing suite, benchmark harness (`w bench`).
- [x] **v0.1.3** — Deterministic RC lifetimes (`CleanupScope`), memory leak tracking (`W_MEM_CHECK=1`).
- [x] **v0.1.4** — Compiler Architecture: `TypeId`, `TypeInterner`, Typed HIR, modular W1 split (`selfhost/src/`), Clang ASan/UBSan integration.
- [x] **v0.2.0** — **Generics, ADTs & Monomorphization**:
  - [x] Phase 1: Parametric polymorphism for `struct Box[T]` and `fn id[T]`, nominal constraints, invariance enforcement.
  - [x] Phase 2: Generic Enums & Algebraic Data Types (ADTs), `Option[T]` $\equiv$ `T?` and `Result[T, E]` $\equiv$ `T ! E` canonical unification, `T025` infinite recursive layout detection.
- [x] **v0.2.1** — **Generic Hardening & Code Bloat Metrics**: Canonical monomorphization cache, specialization telemetry.
- [ ] **v0.3.0** — **Function Types**: First-class function types `fn(A) -> B` and indirect calls without closures.
- [ ] **v0.3.1** — **Weak References & Memory Hardening**: Control block separation for cycle prevention.
- [ ] **v0.4.0** — **Closures & Higher-Order Functions**: Environment capture analysis, heap ARC fat pointers, `map`/`filter`/`reduce`.
- [ ] **v0.5.0** — **Modules & Packages**: Hierarchical package namespace, explicit C FFI bindings.
- [ ] **v0.6.0** — **Standard Library & Tooling**: Standard library (`std.io`, `std.fs`, `std.json`), Language Server Protocol (LSP).

---

## 🤝 Community & Contributing

We welcome contributions from compiler enthusiasts, systems engineers, and language designers!

- **[Contributing Guide](CONTRIBUTING.md)**: Development environment setup, test runner commands, and PR guidelines.
- **[Code of Conduct](CODE_OF_CONDUCT.md)**: Community standards and pledge (Contributor Covenant v2.1).
- **[Security Policy](SECURITY.md)**: Vulnerability disclosure guidelines and supported release lines.
- **[Architecture Decision Records (ADRs)](docs/adr/)**: Formal records of major design choices.
- **[Language Specifications](SPEC.md)**: Formal syntax, type system, and semantics specification.

---

## 📄 License

W is distributed under the permissive **MIT License**. See [LICENSE](LICENSE) for details.
