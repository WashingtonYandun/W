# Wysna Programming Language

[![CI](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="Wysna language mascot" width="160">
</p>

Wysna is an experimental statically typed language for native programming, CLI tools, and high-performance applications. Wysna Seed compiles to portable C99 and combines deterministic reference counting (ARC), copy-on-write (CoW) value semantics, explicit error unions, and controlled C interoperability.

This branch prepares Wysna `0.5.0`. Wysna Seed is the reference compiler and primary production implementation. Wysna Compiler is a modular self-hosted compiler for bootstrap; its supported subset is measured by the four-engine matrix.

---

## Compiler Architecture and Naming

Wysna distinguishes the language from its two compiler implementations. The self-hosted compiler is not yet the default production pipeline.

| Component | Public name | Internal identifier | Implementation language | Role |
| :--- | :--- | :---: | :--- | :--- |
| **Language** | **Wysna** | `wysna` | — | Specification and grammar (`.wysna`) |
| **Reference compiler** | **Wysna Seed** | `seed` | Python | Reference semantics, type interner, HIR/MIR, and default C99 pipeline |
| **Self-hosted compiler** | **Wysna Compiler** | `selfhost` | Wysna | Independent bootstrap compiler with a narrower, measured feature profile |
| **Bootstrap stage 1** | **Stage 1** | `stage1` | Native C99 (compiled by Seed) | First self-hosted compiler binary (`compiler0.c` &rarr; `stage1`) |
| **Bootstrap stage 2** | **Stage 2** | `stage2` | Native C99 (recompiled by Stage 1) | Compiler binary at the deterministic fixed point (`compiler1.c` &rarr; `stage2`) |

### Wysna Seed Compiler Pipeline

Wysna Seed uses multiple stages for type analysis and portable native code generation. Wysna Compiler is a separate self-hosted implementation that currently emits C99 directly.

| Stage | Component | Responsibility | Output representation |
| :--- | :--- | :--- | :--- |
| **Seed frontend** | Lexer and Pratt parser | UTF-8 scanning, operator precedence, and syntax diagnostics | Abstract syntax tree (`AST`) |
| **Seed semantics** | Type checker and scopes | Symbol resolution, nominal typing, and monomorphization | Typed high-level IR (`HIR`) |
| **Seed middle end** | Control-flow graph and MIR | Basic blocks, projections, ownership verification, and CoW operations | Verified middle-level IR (`MIR`) |
| **Seed backend** | C99 generator | MIR-to-C99 translation, ARC, and literal pooling | C99 translation unit (`.c`) |
| **Native compilation** | C toolchain (`clang` / `gcc`) | Compilation and linking against `wysna_runtime.h` and `wysna_host.h` | Standalone executable (`.exe` / ELF / Mach-O) |
| **Self-hosting** | Wysna Compiler | Direct C99 emission; the fixed point validates deterministic output, not IR parity | Native self-hosted binary (`stage2`) |

---

## Engine Parity and Conformance

Every core and standard-library function is continuously checked across four engines:

| Engine | Role | Implementation | Status |
| :--- | :--- | :--- | :--- |
| **`interpreter`** | Reference behavior | Direct AST interpretation in Python (Wysna Seed) | 203/203 (100.0%) |
| **`ast`** | Secondary oracle | Direct C99 generation from AST (Wysna Seed) | 203/203 (100.0%) |
| **`hir`** | Primary production pipeline | Typed HIR &rarr; verified MIR &rarr; C99 backend (Wysna Seed) | 203/203 (100.0%) |
| **`selfhost`** | Self-hosted compiler | Native Wysna Compiler executable (`stage2`) | 203/203 (100.0%) |

See [docs/ENGINE_PARITY_MATRIX.md](docs/ENGINE_PARITY_MATRIX.md) for details and function categories.

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
wysna run <file.wysna> [-- args...]    # Execute with program arguments
wysna check <file.wysna>               # Parse and type-check without code execution
wysna check --output-format=json-v1 <file.wysna>  # Emit a versioned machine-readable result
wysna fmt --output-format=json-v1 <file.wysna>    # Return formatted source as a JSON artifact
wysna build <file.wysna> -o <bin>      # Compile to native standalone executable
wysna emit-c <file.wysna> -o <out.c>   # Generate human-readable portable C99 code
wysna fmt <file.wysna>                 # Format source while preserving comments and layout
wysna lsp                              # Launch Language Server Protocol daemon (stdio)
wysna test                             # Run full test suite across all 4 execution engines
wysna bench                            # Run self-hosted performance benchmarks
```

`check`, `fmt`, `emit-c`, and `build` also accept `--output-format=json-v1`. The
formatter returns inline source content; code and binary generation report artifact
paths and SHA-256 hashes. The default text output and legacy `--json` format remain
unchanged when the option is omitted.

Arguments after `--` are available through `args()`. The interpreter uses `"wysna"` as
`args()[0]`; a native executable receives the operating system's argument vector.

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
