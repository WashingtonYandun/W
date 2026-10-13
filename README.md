# W Programming Language (`v0.1`)

> **W = Compact + Deterministic + Statically Typed + Self-Hostable.**  
> *A small, statically typed programming language optimized for semantic density, deterministic tooling, and reliable code generation by humans and AI systems.*

---

## Overview

**W (`v0.1.1`)** is a statically typed, value-semantics programming language. W includes a self-hosting compiler written entirely in W ([`selfhost/w1.w`](selfhost/w1.w)), bootstrapped from the Python `W0` reference implementation and emitting portable C99.

### Core Properties
1. **31 Keywords:**
   - **Core & Control Flow (22):** `fn`, `let`, `mut`, `struct`, `enum`, `import`, `if`, `elif`, `else`, `for`, `while`, `in`, `match`, `return`, `break`, `continue`, `true`, `false`, `none`, `and`, `or`, `not`.
   - **Object-Oriented Programming (9):** `class`, `interface`, `extends`, `implements`, `new`, `this`, `super`, `public`, `private`.
2. **Explicit Nullability & Fallibility:**
   - Types are non-nullable by default (`str` vs `str?`).
   - Functions declare explicit error channels (`T ! E`) without stack-unwinding exceptions.
   - Unified postfix `?` propagation for both `T?` and `T ! E`, plus inline `else err { ... }` recovery and `??` null-coalescing.
3. **Dual Value & Reference Semantics (OOP + FP-Ready):**
   - **Pure Value Semantics (Deterministic RC + Copy-on-Write):** Collections (`list[T]`, `dict[K, V]`) and `struct` records behave as independent values that share memory via lightweight single-threaded reference counting (`int32_t refcount`) and clone on mutation (`w_cow_detach`) when `refcount > 1`.
   - **Java-Style OOP (`class` & `interface`):** Classes support single inheritance (`extends`), multiple interface implementation (`implements`), `public`/`private` field and method encapsulation, constructors (`fn init`), `this`, `super`, reference identity semantics (`ClassName(...)` or `new ClassName(...)`), and runtime polymorphism / dynamic method dispatch.
4. **UTF-8 Code-Point Strings:**
   - Strings are stored as UTF-8, while `len(s)`, `s[i]`, `slice(s, a, b)`, `ord(s)`, and `chr(c)` operate on Unicode scalar values (`len("José") == 4`, `"José"[3] == "é"`, `len(bytes("José")) == 5`).
5. **Verified 3-Stage Self-Hosting Fixed Point:**
   - `W0` compiles `selfhost/w1.w` $\rightarrow$ `compiler0.c` $\rightarrow$ `w1_stage1`
   - `w1_stage1` compiles `selfhost/w1.w` $\rightarrow$ `compiler1.c` $\rightarrow$ `w1_stage2`
   - `w1_stage2` compiles `selfhost/w1.w` $\rightarrow$ `compiler2.c`
   - $\text{SHA256}(\texttt{compiler0.c}) == \text{SHA256}(\texttt{compiler1.c}) == \text{SHA256}(\texttt{compiler2.c})$

---

## Quick Start & Installation

**Requirements:** `python3` ($\ge 3.10$) and a C99 compiler (`clang` or `gcc`). Zero external Python dependencies are needed.

```bash
git clone https://github.com/WashingtonYandun/W.git
cd W

# 1. Pre-build the Stage-2 native W1 compiler and install 'w' globally (~/.local/bin/w)
./install.sh
# (Or via Makefile / pip):
# make install
# pip install -e .

# 2. Verify installation & run the 181-test conformance suite
w version
w test
```

---

## Language Tour

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

fn describe(task: Task) -> str {
    match task.status {
        Status.Pending => {
            return "pending: " + task.title
        }
        Status.Active => {
            return "active: " + task.title
        }
        Status.Done => {
            return "done: " + task.title
        }
    }
}

fn find_title(tasks: list[Task], target_id: int) -> str? {
    for idx, t in enumerate(tasks) {
        if t.id == target_id {
            return t.title
        }
    }
    return none
}

fn main() -> unit {
    let a = [1, 2, 3]
    let mut b = a
    b.append(4) # Copy-on-Write: `a` remains [1, 2, 3]
    print(a, b)

    let tasks = [
        Task { id: 1, title: "Design SPEC v0.1", status: Status.Done },
        Task { id: 2, title: "Self-host W1", status: Status.Active },
    ]
    print(describe(tasks[1]))
    print(find_title(tasks, 2) ?? "not found")
}
```

---

## CLI Usage (`w` / `./w`)

The canonical `w` CLI supports interpretation, static type checking, formatting, AST inspection, C99 emission, and native binary compilation (via either `W0` or the self-hosted `W1` native compiler with `--selfhost`):

```bash
# Run a .w file via the W0 interpreter
./w run examples/01_hello_world.w

# Static type checking (human-readable or structured JSON diagnostics)
./w check selfhost/w1.w
./w check examples/03_enums_and_match.w --json

# Canonical idempotent code formatter
./w fmt examples/01_hello_world.w
./w fmt examples/01_hello_world.w --write

# Inspect AST or lexical token stream
./w ast examples/01_hello_world.w --json
./w tokens examples/01_hello_world.w

# Transpile W to portable C99 (using W0 or self-hosted W1)
./w emit-c examples/05_utf8_and_algorithms.w -o out.c
./w emit-c --selfhost examples/05_utf8_and_algorithms.w -o out_w1.c

# Compile W directly to a native executable (using W0 or self-hosted W1)
./w build examples/05_utf8_and_algorithms.w -o app
./w build --selfhost examples/05_utf8_and_algorithms.w -o app_w1

# Run the full 13-phase conformance & self-hosting test suite
./w test

# Run the three-engine differential oracle (W0 Interpreter == W0 C99 == W1 Native)
./w test --differential 25

# Run the compiler fuzz suite (0 internal tracebacks invariant)
./w test --fuzz 200
```

---

## Runnable Examples (`examples/`)

| Example | Features Demonstrated |
| :--- | :--- |
| [`examples/01_hello_world.w`](examples/01_hello_world.w) | Functions, explicit types, inclusive ranges (`1..=limit`), loops |
| [`examples/02_value_semantics_cow.w`](examples/02_value_semantics_cow.w) | Deterministic RC + Copy-on-Write value semantics across `list`, `dict`, and `struct` |
| [`examples/03_enums_and_match.w`](examples/03_enums_and_match.w) | `enum`, named `struct` initialization, exhaustive `match` expressions, `enumerate()` |
| [`examples/04_optionals_and_errors.w`](examples/04_optionals_and_errors.w) | `T?`, `??` coalescing, `T ! E` fallible functions, postfix `?`, `else err` recovery |
| [`examples/05_utf8_and_algorithms.w`](examples/05_utf8_and_algorithms.w) | UTF-8 code-point indexing (`"José"[3] == "é"`), `bytes()`, binary search |
| [`examples/06_game_of_life.w`](examples/06_game_of_life.w) | Conway's Game of Life (Glider simulation using `struct`, 2D grid indexing, and CoW state transitions) |
| [`examples/07_oop_polymorphism.w`](examples/07_oop_polymorphism.w) | Java-style OOP (`interface`, `class`, `extends`, `implements`, `public`/`private`, `super`, reference semantics, and dynamic dispatch) alongside `struct` CoW |

---

## Editor Support (VS Code / Cursor / Antigravity)

Syntax highlighting and bracket/comment configuration for `.w` files are included in [`editors/vscode-w/`](editors/vscode-w/README.md):

```bash
# VS Code
ln -sfn "$(pwd)/editors/vscode-w" ~/.vscode/extensions/w-lang-0.1.0

# Cursor
ln -sfn "$(pwd)/editors/vscode-w" ~/.cursor/extensions/w-lang-0.1.0

# Antigravity
ln -sfn "$(pwd)/editors/vscode-w" ~/.antigravity/extensions/w-lang-0.1.0
```

---

## Repository Architecture

| Path | Description |
| :--- | :--- |
| [`SPEC.md`](SPEC.md) | Frozen W v0.1 Language Specification |
| [`w`](w) / [`main.py`](main.py) | Unified CLI entrypoint (`run`, `check`, `fmt`, `ast`, `tokens`, `emit-c`, `build`, `test`, `version`) |
| [`install.sh`](install.sh) / [`Makefile`](Makefile) | One-command toolchain installer and build automation |
| [`pyproject.toml`](pyproject.toml) | PEP 621 package configuration for `pip` / `pipx` |
| [`lexer/Lexer.py`](lexer/Lexer.py) | W v0.1 Lexer (31 keywords, strict numbers, UTF-8 escapes, spans) |
| [`parser/Parser.py`](parser/Parser.py) | Recursive descent parser with 12-level operator precedence |
| [`node/NodeType.py`](node/NodeType.py) | Canonical AST nodes with JSON serialization (`w_ast_version: "0.1"`) |
| [`checker/TypeChecker.py`](checker/TypeChecker.py) | Two-pass static type checker, OOP subtyping/visibility, nullability/error enforcement, exhaustive `match` |
| [`formatter/Formatter.py`](formatter/Formatter.py) | Deterministic, idempotent source code formatter (`w fmt`) |
| [`runtime/Interpreter.py`](runtime/Interpreter.py) | Reference W0 runtime with deterministic RC + Copy-on-Write value semantics and OOP dynamic dispatch |
| [`codegen/CCodeGen.py`](codegen/CCodeGen.py) | W0 C99 code generator |
| [`runtime/w_runtime.h`](runtime/w_runtime.h) | Single-header C99 runtime (deterministic RC + CoW, `W_OBJECT` reference types, UTF-8 code points, collections, I/O) |
| [`selfhost/w1.w`](selfhost/w1.w) | **Self-hosted W1 compiler** written entirely in W |
| [`run_conformance.py`](run_conformance.py) | Automated 13-phase conformance test runner (190/190 tests) |
| [`tests/differential/differential_test.py`](tests/differential/differential_test.py) | Three-engine differential oracle & compiler fuzz suite |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Cross-platform CI pipeline (Linux & macOS) |

---

## Running the Conformance & Self-Hosting Suite

```bash
./w test
```

Verifies all **13 phases (190 / 190 tests)**:
1. **Lexer Valid (13/13)**
2. **Lexer Invalid (7/7)**
3. **Parser Valid (19/19)**
4. **Parser Invalid (9/9)**
5. **Checker Valid (14/14)**
6. **Checker Invalid (23/23)**
7. **Error Handling (2/2)**
8. **Formatter Idempotence (`w fmt`) (25/25)**
9. **Runtime W0 Interpreter (24/24)**
10. **C99 Native Backend W0 (23/23)**
11. **W1 Stage-2 Native Compiler Runtime Parity (23/23)**
12. **Showcase Examples E2E Suite (7/7)**
13. **3-Stage Fixed-Point Bootstrap (`1/1`)**

---

## Language Roadmap

| Version | Milestone | Scope |
| :--- | :--- | :--- |
| **`v0.1.0`** | **Core + Self-Host + OOP** ✅ | 31 keywords, pure value CoW, Java-style OOP, C99 backend, 3-stage `W1` self-hosting fixed point, CLI & CI |
| **`v0.1.1`** | **Harden & Oracle** ✅ | Formalized semantic guarantees, recursive nested CoW, constructor calls without `new`, $L \rightarrow R$ C99 sequence points, 3-engine differential oracle & fuzzer |
| **`v0.1.2`** | **Diagnostics & Stress** | Stable diagnostic codes (`W0xxx`–`W4xxx`), unified JSON diagnostics, full-behavior differential oracle, reproducible stress fuzzing, benchmark harness (`w bench`), HIR & `TypeId` architecture specs |
| **`v0.2`** | **Generics + Monomorphization** | Parametric polymorphism (`fn`, `struct`, `enum`, `class`) compiled via monomorphization with container invariance |
| **`v0.3`** | **Function Types + Typed HIR** | First-class `fn(A) -> B` types and shared `AST -> Typed HIR -> C99` lowering pipeline |
| **`v0.4`** | **Closures + HOFs** | Anonymous functions, value-captured closures, and typed `map` / `filter` / `fold` |
| **`v0.5`** | **Modules + Self-Host Split** | Scoped module system and modular decomposition of `selfhost/w1.w` into multi-file `.w` compiler passes |
| **`v0.6`** | **Stdlib + LSP** | Standard library (`std.io`, `std.fs`, `std.json`, `std.testing`) and Language Server Protocol (LSP) |


