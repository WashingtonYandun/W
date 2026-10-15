# Expansión experimental (E01–E04)

W0/HIR es el compilador de referencia. W1 es un bootstrap experimental: acepta un subconjunto y no sustituye al checker de W0. Esta nota describe lo que existe hoy más allá del núcleo congelado de `SPEC.md`.

## E01 · Funciones como valores

Las firmas `fn(T1, T2) -> R` son invariantes. Se pueden asignar funciones libres, pasarlas como argumentos y devolverlas. La llamada a través de un valor usa un adaptador C uniforme; no se convierten punteros entre firmas incompatibles.

W1 comprueba firmas sobre AST, no sobre nombres de fixtures.

## E02 · Closures

La forma `|x| => expr` y `|a, b| { ... }` captura por valor. Listas, diccionarios y structs se copian como snapshots CoW. Las clases conservan identidad con una referencia fuerte. El entorno vive en el heap y se libera con ARC. No hay captura de frames de stack.

## E03 · Módulos públicos y FFI C

`pub` exporta; `import "archivo.w" as nombre` resuelve nombres calificados. `extern "C"` admite escalares de ancho explícito y handles `opaque`. W no transfiere su allocator al código C. Enlaza bibliotecas con `--link-lib`.

## E04 · OOP genérico, stdlib y LSP

`class Repository[T]` e `interface Collection[T]` se especializan en W0. W1 no implementa esa especialización. La stdlib se importa como `std/io`, `std/text`, `std/bytes` y `std/algorithms`. `./w lsp` reutiliza el checker y los spans del lexer.

Los contratos ejecutables están en `tests/unit/test_expansion_contracts.py`. El corpus público de 107 fixtures de [ENGINE_PARITY_MATRIX.md](ENGINE_PARITY_MATRIX.md) no incluye esos casos.
