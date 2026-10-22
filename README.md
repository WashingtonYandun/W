# Wysna Programming Language

[![CI](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="Wysna language mascot" width="160">
</p>

Wysna is an experimental, statically typed programming language designed for native systems programming, CLI tooling, and high-performance applications. Wysna Seed compiles programs to portable C99 and combines deterministic reference counting (ARC), copy-on-write (CoW) value semantics, explicit error unions, and a controlled C interoperability layer.

The current release is `0.4.0a1` (alpha). Wysna Seed serves as the reference implementation, while Wysna Compiler is the self-hosted compiler verified against a 4-engine parity suite.

---

## Compiler Architecture & Naming

Wysna defines a clear separation between the language, its reference implementation, and its self-hosted production compiler:

| Component | Public Name | Internal Identifier | Implementation Language | Role |
| :--- | :--- | :---: | :--- | :--- |
| **Language** | **Wysna** | `wysna` | — | Language specification & grammar (`.wysna`) |
| **Reference Compiler** | **Wysna Seed** | `seed` | Python | Source of truth, type interner & bootstrap seed (formerly W0) |
| **Self-Hosted Compiler** | **Wysna Compiler** | `selfhost` | Wysna | Production self-hosted compiler (formerly W1) |
| **Bootstrap Stage 1** | **Stage 1** | `stage1` | Native C99 (compiled by Seed) | First self-hosted compiler binary (`compiler0.c` &rarr; `stage1`) |
| **Bootstrap Stage 2** | **Stage 2** | `stage2` | Native C99 (recompiled by Stage 1) | Deterministic fixed-point compiler binary (`compiler1.c` &rarr; `stage2`) |

### Multi-Stage Compiler Pipeline

Wysna implements a multi-stage compiler pipeline designed for verifiable transformations, deterministic memory safety, and portable native code generation:

| Stage | Component | Responsibility | Output Representation |
| :--- | :--- | :--- | :--- |
| **Frontend** | Lexer & Pratt Parser | UTF-8 scanning, operator-precedence parsing, and syntax diagnostics | Abstract Syntax Tree (`AST`) |
| **Semantic Analysis** | Type Checker & Scopes | Scope-based symbol resolution, nominal type checking, and monomorphization | Typed High-Level IR (`HIR`) |
| **Mid-Level IR** | Control-Flow Graph & MIR | Basic blocks, place projections, borrow checking, and CoW detach injection | Verified Mid-Level IR (`MIR`) |
| **Backend** | C99 Code Generator | Translation of MIR to clean C99 code, ARC reference counting, and literal pooling | C99 Translation Unit (`.c`) |
| **Native Compilation** | C Toolchain (`clang` / `gcc`) | Native compilation and linking against `wysna_runtime.h` and `wysna_host.h` | Standalone Executable (`.exe` / ELF / Mach-O) |
| **Self-Hosting** | Wysna Compiler | Bootstrap pipeline verifying fixed-point identity (`compiler0.c == compiler1.c`) | Self-Hosted Native Binary (`stage2`) |

---

## Engine Parity & Conformance

Every core language feature and standard library capability is continuously verified across 4 execution engines:

| Engine | Role | Implementation | Status |
| :--- | :--- | :--- | :--- |
| **`interpreter`** | Reference behavior | Direct AST tree-walk evaluation in Python (Wysna Seed) | 202/202 (100.0%) |
| **`ast`** | Secondary baseline | Direct AST to C99 code generation (Wysna Seed) | 202/202 (100.0%) |
| **`hir`** | Primary production pipeline | Typed HIR &rarr; Verified MIR &rarr; C99 backend (Wysna Seed) | 202/202 (100.0%) |
| **`selfhost`** | Self-hosted compiler | Wysna Compiler native executable (`stage2`) | 202/202 (100.0%) |

See [docs/ENGINE_PARITY_MATRIX.md](docs/ENGINE_PARITY_MATRIX.md) for full breakdown and feature classifications.

---

## Quick Start

### Windows: Standalone Installer

Download `wysna-<version>-windows-x64-setup.exe` from [Wysna Releases](https://github.com/WashingtonYandun/Wysna/releases):

1. Run the `-setup.exe` installer.
2. Keep the default option to add Wysna to your system `PATH`.
3. Open a new terminal (PowerShell or CMD) and verify the installation:

```powershell
wysna version
```

Create a simple `hello.wysna` file:

```wysna
print("Hello from Wysna!")
```

Run directly via the interpreter or compile to a native standalone executable:

```powershell
wysna run hello.wysna
wysna build hello.wysna -o hello.exe
.\hello.exe
```

The standalone installer bundles a private Python runtime and a portable C toolchain: it works fully offline, requires no administrator privileges, and has no dependency on Visual Studio or MSVC build tools.

### macOS & Linux: Source Checkout

Requirements: Python 3.10 or higher and a C99 compiler (`clang` or `gcc`).

```sh
git clone https://github.com/WashingtonYandun/Wysna.git
cd Wysna
./wysna --version
./wysna run examples/01_hello_world.wysna
./wysna test
```

Compiling to a native executable:

```sh
./wysna build examples/01_hello_world.wysna -o build/hello
./build/hello
```

---

## Language Highlights

### 1. Error Unions & Explicit Handling (`T ! E`)

Errors are first-class values and must be handled explicitly with `else` blocks:

```wysna
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

```wysna
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

```wysna
let original = [1, 2, 3, 4]
let mut copy = original   # Shares storage until mutation
copy.append(5)
print(original)           # [1, 2, 3, 4]
print(copy)               # [1, 2, 3, 4, 5]
```

### 4. Bounded Binary I/O & Scoped Resources

```wysna
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

Wysna provides a focused, high-performance standard library:

| Module | Description | Key Functions & Types |
| :--- | :--- | :--- |
| **`std/buffer`** | Fast bounded byte storage | `Bytes`, `size()`, `get()`, `append()`, `close()` |
| **`std/files`** | Streaming file I/O | `File`, `open()`, `read()`, `write()`, `is_open()`, `close()` |
| **`std/fs`** | Portable filesystem operations | `exists()`, `size()`, `mkdir()`, `remove()`, `rename()` |
| **`std/parse`** | Strict string parsing | `parse_int()`, `parse_float()` |
| **`std/json`** | JSON parsing and deterministic serialization | `parse()`, `stringify()`, typed `Value` constructors and accessors |
| **`std/text`** | String transformation utilities | `split()`, `join()`, `replace()`, `trim()`, `find()` |
| **`std/path`** | Cross-platform path handling | `join()`, `dirname()`, `basename()` |
| **`std/resources`** | Deterministic resource scopes | `Resource`, `acquire()`, `scope()`, `borrow()`, `close()` |
| **`std/algorithms`** | Functional primitives | `map`, `fold`, `sort` |

See [docs/STDLIB.md](docs/STDLIB.md) for full API reference and examples.

---

## CLI & Tooling

```text
wysna run <file.wysna>                 # Execute directly with reference interpreter
wysna check <file.wysna>               # Parse and type-check without code execution
wysna build <file.wysna> -o <bin>      # Compile to native standalone executable
wysna emit-c <file.wysna> -o <out.c>   # Generate human-readable portable C99 code
wysna fmt <file.wysna>                 # Format source while preserving comments and layout
wysna lsp                              # Launch Language Server Protocol daemon (stdio)
wysna test                             # Run full test suite across all 4 execution engines
wysna bench                            # Run self-hosted performance benchmarks
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
├── runtime/       # C99 runtime headers (wysna_runtime.h, wysna_host.h)
├── selfhost/      # Self-hosted compiler source code (compiler.wysna)
├── stdlib/        # Standard library implementations
├── tests/         # Differential testing harness and conformance suites
├── tooling/       # Language server (LSP) and developer utilities
└── tools/         # Validation, benchmarking, and packaging scripts
```

---

## License

Wysna is distributed under the terms of the [MIT License](LICENSE).
