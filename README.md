# W Programming Language

[![CI](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="W language mascot" width="160">
</p>

W is an experimental, statically typed programming language designed for native systems programming, CLI tooling, and high-performance applications. W0 compiles programs to portable C99 and combines deterministic reference counting (ARC), copy-on-write (CoW) value semantics, explicit error unions, and a controlled C interoperability layer.

The current release is `0.4.0a1` (alpha). W0 serves as the reference implementation, while W1 is the self-hosted compiler verified against a 4-engine parity suite.

---

## Compiler Architecture

W implements a multi-stage compiler pipeline designed for verifiable transformations, deterministic memory safety, and portable native code generation:

| Stage | Component | Responsibility | Output Representation |
| :--- | :--- | :--- | :--- |
| **Frontend** | Lexer & Pratt Parser | UTF-8 scanning, operator-precedence parsing, and syntax diagnostics | Abstract Syntax Tree (`AST`) |
| **Semantic Analysis** | Type Checker & Scopes | Scope-based symbol resolution, nominal type checking, and monomorphization | Typed High-Level IR (`HIR`) |
| **Mid-Level IR** | Control-Flow Graph & MIR | Basic blocks, place projections, borrow checking, and CoW detach injection | Verified Mid-Level IR (`MIR`) |
| **Backend** | C99 Code Generator | Translation of MIR to clean C99 code, ARC reference counting, and literal pooling | C99 Translation Unit (`.c`) |
| **Native Compilation** | C Toolchain (`clang` / `gcc`) | Native compilation and linking against `w_runtime.h` and `w_host.h` | Standalone Executable (`.exe` / ELF / Mach-O) |
| **Self-Hosting (W1)** | Self-Hosted Compiler | Bootstrap pipeline verifying fixed-point identity (`compiler0.c == compiler1.c`) | Self-Hosted Native Binary (`w1`) |

---

## Engine Parity & Conformance

Every core language feature and standard library capability is continuously verified across 4 execution engines:

| Engine | Role | Implementation | Status |
| :--- | :--- | :--- | :--- |
| **`interpreter`** | Reference behavior | Direct AST tree-walk evaluation in Python | 200/200 (100.0%) |
| **`ast`** | Secondary baseline | Direct AST to C99 code generation | 200/200 (100.0%) |
| **`hir`** | Primary production pipeline | Typed HIR &rarr; Verified MIR &rarr; C99 backend | 200/200 (100.0%) |
| **`w1`** | Self-hosted compiler | Native self-hosted W1 executable | 200/200 (100.0%) |

See [docs/ENGINE_PARITY_MATRIX.md](docs/ENGINE_PARITY_MATRIX.md) for full breakdown and feature classifications.

---

## Quick Start

### Windows: Standalone Installer

Download `w-<version>-windows-x64-setup.exe` from [W Releases](https://github.com/WashingtonYandun/W/releases):

1. Run the `-setup.exe` installer.
2. Keep the default option to add W to your system `PATH`.
3. Open a new terminal (PowerShell or CMD) and verify the installation:

```powershell
w version
```

Create a simple `hello.w` file:

```w
print("Hello from W!")
```

Run directly via the interpreter or compile to a native standalone executable:

```powershell
w run hello.w
w build hello.w -o hello.exe
.\hello.exe
```

The standalone installer bundles a private Python runtime and a portable C toolchain: it works fully offline, requires no administrator privileges, and has no dependency on Visual Studio or MSVC build tools.

### macOS & Linux: Source Checkout

Requirements: Python 3.10 or higher and a C99 compiler (`clang` or `gcc`).

```sh
git clone https://github.com/WashingtonYandun/W.git
cd W
./w --version
./w run examples/01_hello_world.w
./w test
```

Compiling to a native executable:

```sh
./w build examples/01_hello_world.w -o build/hello
./build/hello
```

---

## Language Highlights

### 1. Error Unions & Explicit Handling (`T ! E`)

Errors are first-class values and must be handled explicitly with `else` blocks:

```w
import "std/parse"

fn compute_ratio(raw: str, divisor: int) -> int ! str {
    let value = parse.parse_int(raw) else error { return Err("Invalid number format") }
    if divisor == 0 { return Err("Division by zero") }
    return value / divisor
}

fn show_ratio() {
    let result = compute_ratio("42", 2) else error { print(error) return }
    print("Ratio:", result)
}
show_ratio()
```

### 2. Algebraic Data Types & Pattern Matching

```w
enum Status { Active, Suspended(str), Terminated(int, str) }

fn describe(status: Status) -> str {
    return match status {
        Status.Active => "Account is currently active",
        Status.Suspended(reason) => "Suspended: " + reason,
        Status.Terminated(code, message) => "Terminated (" + str(code) + "): " + message
    }
}
print(describe(Status.Active))
```

### 3. Copy-on-Write (CoW) & Memory Management

Collections (lists, dictionaries, and structs) provide value semantics with zero-copy snapshot efficiency:

```w
let original = [1, 2, 3, 4]
let mut copy = original   # Shares storage until mutation
copy.append(5)
print(original)           # [1, 2, 3, 4]
print(copy)               # [1, 2, 3, 4, 5]
```

### 4. Bounded Binary I/O & Scoped Resources

```w
import "std/files"

fn inspect_file(path: str) -> unit ! files.FileError {
    let file = files.open(path, 0)?  # 0 read, 1 truncate/write, 2 append
    let chunk = file.read(4096)?
    print("Read bytes:", chunk.size())
    # File and Bytes release their host storage with their last owner.
    # Use close() explicitly when its status matters.
}
inspect_file("README.md") else error { print(error.operation, error.code) }
```

---

## Standard Library Modules

W provides a focused, high-performance standard library:

| Module | Description | Key Functions & Types |
| :--- | :--- | :--- |
| **`std/buffer`** | Fast bounded byte storage | `Bytes`, `size()`, `get()`, `append()`, `close()` |
| **`std/files`** | Streaming file I/O | `File`, `open()`, `read()`, `write()`, `is_open()`, `close()` |
| **`std/fs`** | Portable filesystem operations | `exists()`, `size()`, `mkdir()`, `remove()`, `rename()` |
| **`std/parse`** | Strict string parsing | `parse_int()`, `parse_float()` |
| **`std/text`** | String transformation utilities | `split()`, `join()`, `replace()`, `trim()`, `find()` |
| **`std/path`** | Cross-platform path handling | `join()`, `dirname()`, `basename()` |
| **`std/resources`** | Deterministic resource scopes | `Resource`, `acquire()`, `scope()`, `borrow()`, `close()` |
| **`std/algorithms`** | Functional primitives | `map`, `fold`, `sort` |

See [docs/STDLIB.md](docs/STDLIB.md) for full API reference and examples.

---

## CLI & Tooling

```text
w run <file.w>                 # Execute directly with reference interpreter
w check <file.w>               # Parse and type-check without code execution
w build <file.w> -o <bin>      # Compile to native standalone executable
w emit-c <file.w> -o <out.c>   # Generate human-readable portable C99 code
w fmt <file.w>                 # Format source while preserving comments and layout
w lsp                          # Launch Language Server Protocol daemon (stdio)
w test                         # Run full test suite across all 4 execution engines
w bench                        # Run self-hosted performance benchmarks
```

---

## Documentation

- [Language specification](SPEC.md): syntax, expressions, and semantics.
- [Type system design](docs/TYPE_SYSTEM_DESIGN.md): nominal checking, inference, and monomorphization.
- [HIR representation](docs/HIR_DESIGN.md) & [MIR representation](docs/MIR_DESIGN.md): intermediate forms and contracts.
- [Ownership & lifetimes](docs/OWNERSHIP_LIFETIME.md): ARC, copy-on-write, weak references, and drop elaboration.
- [Standard library reference](docs/STDLIB.md): complete API documentation for all standard modules.
- [Engine parity matrix](docs/ENGINE_PARITY_MATRIX.md): 4-engine test results and coverage.
- [FFI & C interoperability](docs/FFI_VALIDATION.md): calling C functions and descriptor ABI.
- [Known limits & boundaries](docs/KNOWN_LIMITS.md): current alpha constraints and guidelines.
- [Contributing guide](CONTRIBUTING.md) & [Security policy](SECURITY.md).

---

## Repository Layout

```text
├── checker/       # Semantic analysis, type checking, and monomorphization
├── codegen/       # C99 code generation and literal table emission
├── common/        # Shared platform adapters, locks, and version metadata
├── docs/          # Architecture RFCs, specifications, and design reports
├── error/         # Structured compiler diagnostic codes (W1000-W5000)
├── examples/      # Canonical code examples and language tours
├── formatter/     # Comment-preserving AST code formatter
├── hir/           # High-Level IR data structures and lowering
├── lexer/         # UTF-8 scanner, token definitions, and string escapes
├── mir/           # Mid-Level IR, CFG, place projections, and drop elaboration
├── node/          # AST node definitions
├── parser/        # Pratt parser and grammar rules
├── runtime/       # C99 runtime headers (w_runtime.h, w_host.h)
├── selfhost/      # Self-hosted W1 compiler source code (w1.w)
├── stdlib/        # Standard library implementations
├── tests/         # Differential testing harness and conformance suites
├── tooling/       # Language server (LSP) and developer utilities
└── tools/         # Validation, benchmarking, and packaging scripts
```

---

## License

W is distributed under the terms of the [MIT License](LICENSE).
