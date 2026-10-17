# W Programming Language

[![CI](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml)

<p align="center">
  <img src="assets/wawi.jpg" alt="W language mascot" width="160">
</p>

W is an experimental, statically typed language for native tools and applications. W0 compiles programs to portable C99 and uses deterministic reference counting, copy-on-write value semantics, explicit error handling, and a controlled C interoperability layer.

The current release is `0.4.0a1` (alpha). W0 is the reference compiler. W1 is a self-hosted compiler with a narrower, measured support profile. This project is under active development and is not yet production-stable.

## Quick start

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

W0 provides an interpreter, a secondary AST-to-C backend, and a default typed HIR-to-C99 backend. The verified MIR representation can be inspected with `./w mir`; it is not the native code-generation backend. W1 compiles itself and supports the subset measured in the [engine parity matrix](docs/ENGINE_PARITY_MATRIX.md).

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
