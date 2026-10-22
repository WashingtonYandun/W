# Wysna Programming Language

[![CI](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/Wysna/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="Wysna language mascot" width="160">
</p>

Wysna es un lenguaje experimental de tipado estático para programación nativa, herramientas CLI y aplicaciones de alto rendimiento. Wysna Seed compila a C99 portable y combina conteo de referencias determinista (ARC), semántica de valor copy-on-write (CoW), uniones de error explícitas e interoperabilidad controlada con C.

Esta rama prepara Wysna `0.5.0`. Wysna Seed es el compilador de referencia y la implementación principal de producción. Wysna Compiler es un compilador modular y autoalojado para bootstrap; su subconjunto soportado se mide con la matriz de cuatro motores.

---

## Arquitectura y nombres de los compiladores

Wysna distingue el lenguaje de sus dos implementaciones de compilador. El compilador autoalojado todavía no es la tubería de producción predeterminada.

| Componente | Nombre público | Identificador interno | Lenguaje de implementación | Función |
| :--- | :--- | :---: | :--- | :--- |
| **Lenguaje** | **Wysna** | `wysna` | — | Especificación y gramática (`.wysna`) |
| **Compilador de referencia** | **Wysna Seed** | `seed` | Python | Semántica de referencia, interner de tipos, HIR/MIR y tubería C99 predeterminada |
| **Compilador autoalojado** | **Wysna Compiler** | `selfhost` | Wysna | Compilador independiente de bootstrap, con un perfil de funciones medido y más acotado |
| **Etapa 1 de bootstrap** | **Stage 1** | `stage1` | C99 nativo (compilado por Seed) | Primer binario del compilador autoalojado (`compiler0.c` &rarr; `stage1`) |
| **Etapa 2 de bootstrap** | **Stage 2** | `stage2` | C99 nativo (recompilado por Stage 1) | Binario del compilador en punto fijo determinista (`compiler1.c` &rarr; `stage2`) |

### Tubería del compilador Wysna Seed

Wysna Seed usa varias etapas para el análisis de tipos y la generación de código nativo portable. Wysna Compiler es una implementación autoalojada separada que actualmente genera C99 directamente.

| Etapa | Componente | Responsabilidad | Representación de salida |
| :--- | :--- | :--- | :--- |
| **Frontend de Seed** | Lexer y parser Pratt | Escaneo UTF-8, precedencia de operadores y diagnósticos sintácticos | Árbol de sintaxis abstracta (`AST`) |
| **Semántica de Seed** | Verificador de tipos y scopes | Resolución de símbolos, tipado nominal y monomorfización | IR de alto nivel tipado (`HIR`) |
| **Middle-end de Seed** | Grafo de flujo de control y MIR | Bloques básicos, proyecciones, verificación de ownership y operaciones CoW | IR de nivel medio verificada (`MIR`) |
| **Backend de Seed** | Generador C99 | Traducción de MIR a C99, ARC y agrupación de literales | Unidad de traducción C99 (`.c`) |
| **Compilación nativa** | Toolchain C (`clang` / `gcc`) | Compilación y enlazado contra `wysna_runtime.h` y `wysna_host.h` | Ejecutable independiente (`.exe` / ELF / Mach-O) |
| **Autoalojamiento** | Wysna Compiler | Emisión directa de C99; el punto fijo valida salida determinista, no paridad de IR | Binario nativo autoalojado (`stage2`) |

---

## Paridad de motores y conformidad

Cada función del núcleo y de la biblioteca estándar se verifica continuamente en cuatro motores:

| Motor | Función | Implementación | Estado |
| :--- | :--- | :--- | :--- |
| **`interpreter`** | Comportamiento de referencia | Interpretación directa del AST en Python (Wysna Seed) | 203/203 (100.0%) |
| **`ast`** | Oráculo secundario | Generación directa de C99 desde AST (Wysna Seed) | 203/203 (100.0%) |
| **`hir`** | Tubería principal de producción | HIR tipada &rarr; MIR verificada &rarr; backend C99 (Wysna Seed) | 203/203 (100.0%) |
| **`selfhost`** | Compilador autoalojado | Ejecutable nativo Wysna Compiler (`stage2`) | 203/203 (100.0%) |

Consulta [docs/ENGINE_PARITY_MATRIX.md](docs/ENGINE_PARITY_MATRIX.md) para ver el detalle y las categorías de funciones.

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
