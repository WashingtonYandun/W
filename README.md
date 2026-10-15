# W

[![CI](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml/badge.svg)](https://github.com/WashingtonYandun/W/actions/workflows/ci.yml)

W es un lenguaje experimental con tipos estáticos, compilación a C99 y memoria mediante ARC y copy-on-write. Su objetivo es escribir herramientas y aplicaciones nativas pequeñas con semántica de valores predecible, errores explícitos y acceso controlado a bibliotecas C.

La versión de desarrollo es `0.3.0.dev1`. El lenguaje cambia; no existe todavía una garantía de compatibilidad para producción. El compilador de referencia W0 es la autoridad sobre si un programa es válido; W1 es un compilador escrito en W para un subconjunto estricto (sin genéricos, sin payloads de enum y sin pattern matching sobre `Option`/`Result`). Consulta [la matriz de motores](docs/ENGINE_PARITY_MATRIX.md), [el estado de la expansión](docs/EXPANSION.md) y [los límites conocidos](docs/KNOWN_LIMITS.md).

## Uso

Requiere Python 3.10 o posterior y un compilador C99 para generar ejecutables.

```sh
git clone https://github.com/WashingtonYandun/W.git
cd W
./w run examples/01_hello_world.w
./w check examples/01_hello_world.w
./w build examples/01_hello_world.w -o build/hello
./w test
```

También se puede instalar W0 con `pip install .`. La distribución incluye el frontend, HIR, runtime C, stdlib y LSP. El bootstrap de W1 y la suite de desarrollo requieren el checkout del repositorio.

```w
fn apply(transform: fn(int) -> int, value: int) -> int {
    return transform(value)
}
let offset = 10
let add: fn(int) -> int = |value| => value + offset
print(apply(add, 5))
```

Las closures capturan por valor: conservan snapshots de listas, diccionarios y structs, y no pueden mutar lo capturado. Las clases mantienen identidad y referencias fuertes; los ciclos fuertes requieren referencias débiles explícitas. Las limitaciones conocidas y las decisiones aplazadas están en [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md).

## Módulos y C

Un módulo exporta únicamente declaraciones `pub`:

```w
pub fn double(value: int) -> int { return value * 2 }
```

```w
import "math.w" as math
print(math.double(3))
extern "C" fn sqrt(value: double) -> double
print(sqrt(81.0))
```

La FFI inicial acepta escalares y handles `opaque`. `int32` se comprueba al entrar en C; `int` e `int64` usan enteros de 64 bits. `float` y `double` corresponden a C `double`. Usa `--link-lib m` cuando tu plataforma requiera enlazar libm. Los handles no transfieren ownership de memoria de W.

La stdlib se importa como `import "std/text" as text`. Incluye módulos `io`, `text`, `bytes` y `algorithms`; sus contratos y límites están en [stdlib](docs/STDLIB.md).

## Herramientas

- `./w fmt archivo.w`: formato conservando comentarios.
- `./w emit-c archivo.w -o programa.c`: inspección del C generado; HIR es el backend predeterminado.
- `./w build archivo.w -o programa --sanitize`: ejecución instrumentada con ASan/UBSan.
- `./w lsp`: servidor LSP por stdio, compartiendo el checker y los snapshots de fuentes.
- `./w test --differential 25 --seed 1000`: comparación de motores.

Un `Err` devuelto por `main` se informa por `stderr` como `W4003` y termina el proceso con
un código distinto de cero, para que un programa que falla no sea indistinguible de uno
que tuvo éxito.

## Estructura

- `lexer/`, `parser/`, `node/`, `wtokens/`: frontend y sintaxis.
- `checker/`, `compiler/`: tipos, sesiones, módulos y especializaciones.
- `hir/`, `codegen/`, `runtime/`: representación intermedia, emisión C y ejecución de referencia.
- `selfhost/src/`: fuentes modulares de W1; `selfhost/w1.w` se genera con `python3 tools/bundle_w1.py`.
- `stdlib/`, `tooling/`, `editors/`: biblioteca y herramientas de edición.
- `tests/unit/`, `tests/runtime/`, `tests/types/`, `tests/fuzz/`: contratos, fixtures y fuzzing.
- `examples/`, `bench/`, `tools/`: ejemplos, medición y utilidades.
- `docs/adr/`: decisiones técnicas; `docs/history/`: informes históricos; `docs/KNOWN_LIMITS.md`: lo que W no hace y por qué.

La [especificación](SPEC.md) define el lenguaje. Los informes de hitos describen resultados de su fecha y no reemplazan los contratos actuales.

## Límites conocidos

W1 aún no implementa toda la especialización genérica de W0. El runtime usa ARC de un solo hilo; no ofrece concurrencia de memoria compartida. Los rangos producen listas materializadas y comprueban su tamaño antes de reservar. La FFI no ofrece callbacks C, aritmética de punteros ni transferencia automática de allocators.

El proyecto está bajo [licencia MIT](LICENSE). Para contribuir, consulta [CONTRIBUTING.md](CONTRIBUTING.md).
