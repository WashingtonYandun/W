# W Programming Language (`v0.1`)

> **W = Compact + Deterministic + Statically Typed + Self-Hostable.**  
> *A small, statically typed programming language optimized for semantic density, deterministic tooling, and reliable code generation by humans and AI systems.*

---

## Overview

**W (`v0.1`)** is a statically typed, value-semantics programming language with both a reference interpreter (`W0`) and a self-hosting native C99 compiler (`W1` in [`selfhost/w1.w`](selfhost/w1.w)).

### Core Properties
1. **Exactly 22 Keywords:** `fn`, `let`, `mut`, `struct`, `enum`, `import`, `if`, `elif`, `else`, `for`, `while`, `in`, `match`, `return`, `break`, `continue`, `true`, `false`, `none`, `and`, `or`, `not`.
2. **Explicit Nullability & Fallibility:**
   - Types are non-nullable by default (`str` vs `str?`).
   - Functions declare explicit error channels (`T ! E`) without stack-unwinding exceptions.
   - Unified postfix `?` propagation for both `T?` and `T ! E`, plus inline `else err { ... }` recovery and `??` null-coalescing.
3. **Pure Value Semantics (ARC + Copy-on-Write):**
   - Collections (`list[T]`, `dict[K, V]`) and structs (`struct`) behave as independent values.
   - Assignments share memory via reference counting (`rc`) and automatically clone on mutation (`w_cow_detach`) when `rc > 1`.
4. **UTF-8 Code-Point Strings:**
   - Strings are stored as UTF-8, while `len(s)`, `s[i]`, `slice(s, a, b)`, `ord(s)`, and `chr(c)` operate on Unicode scalar values (`len("José") == 4`, `"José"[3] == "é"`, `len(bytes("José")) == 5`).
5. **Verified 3-Stage Self-Hosting Fixed Point:**
   - `W0` compiles `selfhost/w1.w` $\rightarrow$ `compiler0.c` $\rightarrow$ `w1_stage1`
   - `w1_stage1` compiles `selfhost/w1.w` $\rightarrow$ `compiler1.c` $\rightarrow$ `w1_stage2`
   - `w1_stage2` compiles `selfhost/w1.w` $\rightarrow$ `compiler2.c`
   - $\text{SHA256}(\texttt{compiler0.c}) == \text{SHA256}(\texttt{compiler1.c}) == \text{SHA256}(\texttt{compiler2.c})$

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

## CLI Usage (`./w`)

The canonical `./w` CLI supports interpretation, static type checking, formatting, AST inspection, C99 emission, and native binary compilation:

```bash
# Run a .w file via the W0 interpreter
./w run examples/hello.w

# Static type checking (human-readable or structured JSON diagnostics)
./w check selfhost/w1.w
./w check file.w --json

# Canonical idempotent code formatter
./w fmt file.w
./w fmt file.w --write

# Inspect AST or lexical token stream
./w ast file.w --json
./w tokens file.w --json

# Transpile W to portable C99 (backed by runtime/w_runtime.h)
./w emit-c file.w -o out.c

# Compile W directly to a native executable via clang/gcc
./w build selfhost/w1.w -o w1_native

# Run the full 9-stage conformance & self-hosting test suite
./w test
```

---

## Repository Architecture

| Path | Description |
| :--- | :--- |
| [`SPEC.md`](SPEC.md) | Frozen W v0.1 Language Specification |
| [`w`](w) / [`main.py`](main.py) | Unified CLI entrypoint (`run`, `check`, `fmt`, `ast`, `tokens`, `emit-c`, `build`, `test`) |
| [`lexer/Lexer.py`](lexer/Lexer.py) | W v0.1 Lexer (22 keywords, strict numbers, UTF-8 escapes, spans) |
| [`parser/Parser.py`](parser/Parser.py) | Recursive descent parser with 12-level operator precedence |
| [`ast_nodes.py`](ast_nodes.py) | Canonical AST nodes with JSON serialization (`w_ast_version: "0.1"`) |
| [`checker/TypeChecker.py`](checker/TypeChecker.py) | Two-pass static type checker, nullability/error enforcement, exhaustive `match` |
| [`formatter/Formatter.py`](formatter/Formatter.py) | Deterministic, idempotent source code formatter (`w fmt`) |
| [`interpreter/Interpreter.py`](interpreter/Interpreter.py) | Reference W0 runtime with ARC + Copy-on-Write value semantics |
| [`codegen/CCodeGen.py`](codegen/CCodeGen.py) | W0 C99 code generator |
| [`runtime/w_runtime.h`](runtime/w_runtime.h) | Single-header C99 runtime (ARC + CoW, UTF-8 code points, collections, I/O) |
| [`selfhost/w1.w`](selfhost/w1.w) | **Self-hosted W1 compiler** written in 100% pure W |
| [`run_conformance.py`](run_conformance.py) | Automated 9-stage conformance test runner (164/164 tests) |

---

## Running the Conformance & Self-Hosting Suite

```bash
./w test
```

Verifies all 9 stages:
1. **Lexer Valid (11/11)** & **Lexer Invalid (7/7)**
2. **Parser Valid (13/13)** & **Parser Invalid (7/7)**
3. **Checker Valid (15/15)** & **Checker Invalid (25/25)**
4. **Runtime W0 Interpreter (20/20)**
5. **Formatter Idempotence & Semantic Preservation (26/26)**
6. **C99 Native Backend W0 (20/20)**
7. **W1 Stage-2 Native Compiler Runtime Parity (20/20)** & **3-Stage Fixed-Point Bootstrap**
