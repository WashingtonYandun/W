# The W Programming Language

<p align="center">
  <a href="https://github.com/WashingtonYandun/W/actions"><img src="https://img.shields.io/badge/build-passing-brightgreen?style=flat-square" alt="Build Status"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/conformance-312%2F312%20(100%25)-success?style=flat-square" alt="Conformance Tests"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/sanitizers-ASan%20%7C%20UBSan%20clean-blue?style=flat-square" alt="Sanitizers"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/self--hosting-3--stage%20fixed--point-purple?style=flat-square" alt="Self-Hosting"></a>
  <a href="https://github.com/WashingtonYandun/W"><img src="https://img.shields.io/badge/backend-portable%20C99-orange?style=flat-square" alt="Backend"></a>
  <a href="https://github.com/WashingtonYandun/W/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <strong>Compact &bull; Deterministic &bull; Statically Typed &bull; Self-Hostable Systems Language</strong><br>
  <em>Designed for semantic clarity, deterministic lifetimes, copy-on-write efficiency, and seamless human & AI collaboration.</em>
</p>

---

## ⚡ What is W?

**W** is a modern, statically typed programming language with a modular, self-hosted compiler that emits portable C99. W bridges the gap between high-level expressive programming and predictable, low-level systems engineering.

### Why W?

| Feature | How W Solves It | Benefit |
| :--- | :--- | :--- |
| **Memory Safety** | Pure Value Semantics + Copy-on-Write (CoW) for data, single-threaded ARC for objects | Zero garbage collector pauses; deterministic `CleanupScope` frees memory at scope exit |
| **Nullability & Errors** | Explicit `T?` nullability and `T ! E` error channels with unified postfix `?` operator | No unexpected `null` dereferences; no runtime exception unwinding overhead |
| **Expressive OOP** | Java-style `class`, `interface`, single-inheritance `extends`, `implements`, `super` | Familiar object-oriented modeling with clean encapsulation (`public`/`private`) |
| **Self-Hosting Compiler** | 3-stage bootstrap fixed-point: $\text{SHA256}(c_0) == \text{SHA256}(c_1) == \text{SHA256}(c_2)$ | True compiler autonomy and language stability |
| **Modern Architecture** | Lexer $\to$ Parser $\to$ TypeInterner $\to$ Typed HIR $\to$ HirCCodeGen | Rock-solid multi-pass design ready for Monomorphized Generics and optimizations |
| **Zero Runtime Bloat** | Emits standard C99; single-header runtime (`w_runtime.h`), binaries are $\approx 34\text{ KB}$ | High portability across Linux, macOS, BSD, and embedded targets |

---

## 🚀 Quick Start & Installation

### Prerequisites
- **Python** $\ge 3.10$ (for reference tools)
- **C99 Compiler** (`clang` or `gcc`)
- Zero external package dependencies.

### One-Line Install

```bash
git clone https://github.com/WashingtonYandun/W.git
cd W

# Compile Stage-2 native W1 compiler and install globally to ~/.local/bin/w
./install.sh

# Verify installation & test suite
w version
w test
```

---

## 💻 Language Tour

```w
enum Status {
    Pending
    Active
    Done
}

struct Task {
    id: int
    title: str
    status: Status
}

# Explicit fallibility with T ! E and unified '?' error propagation
fn parse_id(raw: str) -> int ! str {
    if len(raw) == 0 {
        return "empty string"
    }
    return 101 # Simulated parsing
}

# Exhaustive pattern matching over enums
fn describe(task: Task) -> str {
    match task.status {
        Status.Pending => { return "Pending: " + task.title }
        Status.Active  => { return "Active: "  + task.title }
        Status.Done    => { return "Done: "    + task.title }
    }
}

# Object-Oriented Programming with interfaces and classes
interface Printable {
    fn to_string() -> str
}

class Project implements Printable {
    private var name: str
    private var tasks: list[Task]

    fn init(name: str) {
        this.name = name
        this.tasks = []
    }

    public fn add_task(task: Task) -> unit {
        this.tasks.append(task)
    }

    public fn to_string() -> str {
        return "Project '" + this.name + "' with " + str(len(this.tasks)) + " tasks"
    }
}

fn main() -> unit {
    # 1. Pure Value Semantics + Copy-on-Write (CoW)
    let a = [1, 2, 3]
    let mut b = a
    b.append(4) # CoW: 'b' is detached; 'a' remains exactly [1, 2, 3]
    print(a)    # [1, 2, 3]
    print(b)    # [1, 2, 3, 4]

    # 2. Error channel recovery
    let id = parse_id("42") else err {
        print("Failed to parse:", err)
        return
    }

    # 3. Object-Oriented Polymorphism
    let p = Project("W Compiler")
    p.add_task(Task { id: id, title: "Typed HIR Backend", status: Status.Done })
    print(p.to_string())
}
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

# 4. Transpile W to C99 via Typed HIR backend or self-hosted W1
w emit-c --hir examples/05_utf8_and_algorithms.w -o out.c
w emit-c --selfhost examples/05_utf8_and_algorithms.w -o out_w1.c

# 5. Compile directly to optimized native binary
w build --hir examples/05_utf8_and_algorithms.w -o app
w build --selfhost examples/05_utf8_and_algorithms.w -o app_w1

# 6. Run full 312-test conformance suite (100% pass)
w test

# 7. Run AddressSanitizer & UndefinedBehaviorSanitizer suite
w test --sanitize

# 8. Run 3-engine differential testing oracle & compiler fuzzer
w test --differential 50 --seed 20260416
w test --fuzz 2000 --seed 20260416

# 9. Performance benchmarks
w bench
```

---

## 🏛️ Compiler Architecture

W follows a modular compiler architecture designed for formal correctness and maintainability:

```text
Source Code (.w)
       │
       ▼
 ┌──────────┐
 │  Lexer   │  ──▶ 31 Keywords, UTF-8 codepoints, strict numbers
 └────┬─────┘
       ▼
 ┌──────────┐
 │  Parser  │  ──▶ Pratt precedence parser, AST with source spans
 └────┬─────┘
       ▼
 ┌───────────────┐
 │  TypeChecker  │ ──▶ Two-pass analysis, TypeInterner (TypeId), OOP subtyping
 └────┬──────────┘
       ▼
 ┌───────────────┐
 │   Typed HIR   │ ──▶ Canonical High-level Intermediate Representation
 └────┬──────────┘
       │
       ├──▶ Monomorphization (v0.2 Generics)
       │
       ▼
 ┌───────────────┐
 │  HirCCodeGen  │ ──▶ Deterministic CleanupScope ARC, dynamic dispatch, CoW
 └────┬──────────┘
       ▼
  Portable C99 ──▶ Clang / GCC (-O2) ──▶ Native Binary (~34 KB)
```

### Self-Hosted Compiler (`selfhost/src/`)
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

## 🗺️ Roadmap

- [x] **v0.1.0** — Core language, OOP (classes & interfaces), C99 backend, 3-stage self-hosting fixed-point.
- [x] **v0.1.1** — Semantic hardening, recursive nested CoW, constructor desugaring, 3-engine differential oracle.
- [x] **v0.1.2** — Stable diagnostic codes (`W0xxx`–`W4xxx`), fuzzing suite, benchmark harness (`w bench`).
- [x] **v0.1.3** — Deterministic RC lifetimes (`CleanupScope`), memory leak tracking (`W_MEM_CHECK=1`).
- [x] **v0.1.4** — Compiler Architecture Foundation: `TypeId`, `TypeInterner`, Typed HIR, modular W1 split (`selfhost/src/`), Clang ASan/UBSan integration.
- [ ] **v0.2.0** — **Generics & Monomorphization**: Parametric polymorphism for `struct` and functions (`Box[T]`, `Pair[A, B]`, `fn id[T]`), invariance enforcement.
- [ ] **v0.3.0** — **Function Types**: First-class function types `fn(A) -> B` and callable representation.
- [ ] **v0.4.0** — **Closures & HOFs**: Capture analysis, anonymous functions, `map`/`filter`/`reduce`.
- [ ] **v0.5.0** — **Modules & Packages**: Hierarchical package namespace, explicit FFI integration.
- [ ] **v0.6.0** — **Stdlib & Tooling**: Standard library (`std.io`, `std.fs`, `std.json`), Language Server Protocol (LSP).

---

## 📄 License

W is distributed under the permissive **MIT License**. See [LICENSE](LICENSE) for details.
