# W Programming Language

[![CI](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="W language mascot" width="160">
</p>

W is an experimental, statically typed language for native tools and applications. W0 compiles programs to portable C99 and uses deterministic reference counting, copy-on-write value semantics, explicit error handling, and a controlled C interoperability layer.

The current release is `0.4.0a1` (alpha). W0 is the reference compiler. W1 is a self-hosted compiler with a narrower, measured support profile. This project is under active development and is not yet production-stable.

## Quick start

### Windows: instalador autónomo

En las [descargas de W](https://github.com/WashingtonYandun/W/releases), busca el archivo
`w-<version>-windows-x64-setup.exe` de la versión que incluya el instalador.
El wheel `.whl` es una distribución alternativa para usuarios de Python.

1. Descarga y abre el archivo `-setup.exe`.
2. Instala para tu usuario y conserva la opción de agregar W al PATH.
3. Abre **W Language** desde Inicio, o abre una terminal nueva y ejecuta:

```powershell
w version
```

Para probarlo, guarda `print("Hola, W")` en `hello.w` y ejecuta:

```powershell
w run hello.w
w build hello.w -o hello.exe
.\hello.exe
```

El instalador incluye Python y una toolchain C privada: no necesitas instalar Python,
usar pip, crear/activar entornos virtuales ni instalar Visual Studio. Funciona sin
administrador y sin conexión después de descargarlo. El primer build puede tardar más
porque prepara la caché del compilador C. El alcance inicial es Windows 10/11 x64 y W0;
W1, `w test` y `w bench` requieren el repositorio fuente. Las bibliotecas C externas
usadas mediante FFI se proporcionan por separado.

Si una terminal estaba abierta durante la instalación, ciérrala y abre otra. También
puedes usar el acceso directo del menú Inicio, que prepara su propia terminal. Si `w`
coincide con otro comando instalado, usa `wlang`. Para reparar archivos, ejecuta otra
vez el instalador. Para quitar W, usa **Aplicaciones instaladas** en Windows; se elimina
únicamente la entrada del PATH creada por W y se conservan tus proyectos.

Los builds de CI generan el instalador y su informe de pruebas. Un artefacto generado
no equivale a una release publicada ni a un instalador firmado; la firma pública y la
experiencia de SmartScreen se verifican por separado.

### Source checkout and other platforms

Requirements: Python 3.10 or later and a C99 compiler (`clang` or `gcc`).

```sh
git clone https://github.com/WashingtonYandun/W.git
cd W
./w --version
./w run examples/01_hello_world.w
./w test
```

Build a native executable with:

```sh
./w build examples/01_hello_world.w -o build/hello
./build/hello
```

## Language example

```w
fn apply(transform: fn(int) -> int, value: int) -> int {
    return transform(value)
}

let offset = 10
let add: fn(int) -> int = |value| => value + offset
print(apply(add, 5))
```

Closures capture values. Lists, dictionaries, and structs use copy-on-write snapshots; classes keep reference identity. See the [ownership model](docs/OWNERSHIP_LIFETIME.md) and [known limits](docs/KNOWN_LIMITS.md).

## Compiler and tools

W0 provides an interpreter, a secondary AST-to-C backend, and a default typed HIR → verified MIR → C99 backend. `./w mir` prints the verified MIR representation. W1 compiles itself and supports the subset measured in the [engine parity matrix](docs/ENGINE_PARITY_MATRIX.md).

- `./w run path.w`: execute with W0.
- `./w check path.w`: parse and type-check without execution.
- `./w build path.w -o program`: compile a native executable.
- `./w emit-c path.w -o program.c`: emit C99 for inspection.
- `./w fmt path.w`: format source while preserving comments.
- `./w lsp`: start the stdio language server.
- `./w test`: run the conformance suite.

The FFI supports scalar values and opaque handles. It does not transfer ownership of W-managed memory. If `main` returns an `Err`, W emits diagnostic `W4003` and exits non-zero.

## Documentation

- [Language specification](SPEC.md): syntax and language semantics.
- [Type system](docs/TYPE_SYSTEM_DESIGN.md), [HIR](docs/HIR_DESIGN.md), and [MIR](docs/MIR_DESIGN.md): compiler representations and contracts.
- [Ownership and lifetimes](docs/OWNERSHIP_LIFETIME.md): ARC, copy-on-write, weak references, and cleanup.
- [Engine support](docs/ENGINE_PARITY_MATRIX.md) and [known limits](docs/KNOWN_LIMITS.md): tested capabilities and boundaries.
- [C interoperability](docs/FFI_VALIDATION.md) and [standard library](docs/STDLIB.md).
- [Contributing](CONTRIBUTING.md) and [security policy](SECURITY.md).

## Repository layout

- `lexer/`, `parser/`, `node/`: language frontend.
- `checker/`, `compiler/`: type checking, modules, and specialization.
- `hir/`, `mir/`, `codegen/`, `runtime/`: intermediate representations, C generation, and runtime.
- `selfhost/src/`: modular W1 source; `selfhost/w1.w` is bundled from these files.
- `stdlib/`, `tooling/`, `editors/`: libraries and developer tooling.
- `tests/`, `examples/`, `bench/`, `tools/`: regression suites, examples, benchmark workloads, and utilities.

W is licensed under the [MIT License](LICENSE).
