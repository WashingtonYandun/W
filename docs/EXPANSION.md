# Expansión experimental (E01–E04)

W0/HIR es el compilador de referencia. W1 es un compilador autoalojado con un perfil de
soporte más reducido. Esta nota describe las capacidades añadidas en la Fase E y distingue
las capacidades implementadas de las que tienen paridad probada entre motores.

| Hito | Capacidad | Cobertura comprobada |
| :--- | :--- | :--- |
| E01 | Funciones como valores y llamadas indirectas | W0: intérprete, AST C99 y HIR C99. W1: funciones como valores y llamadas indirectas en los casos de `tests/functions/`. |
| E02 | Closures con captura por valor | W0: intérprete, AST C99 y HIR C99. W1: las formas cubiertas por los casos de closures de `tests/functions/`. |
| E03 | Módulos `pub`/`import` y FFI C | W0: módulos comprobados y FFI escalar en AST/HIR. W1: expansión y calificación de imports existen, pero no equivalen a sesiones tipadas compartidas; FFI y paridad de módulos no están cubiertas aquí. |
| E04 | OOP genérico, stdlib y LSP | W0: OOP genérico y stdlib en intérprete/AST/HIR; LSP sobre el checker de W0. W1: no se afirma paridad para estos componentes. |

Las firmas `fn(T1, T2) -> R` son invariantes. Las closures capturan por valor: listas,
diccionarios y structs conservan snapshots CoW; las clases mantienen identidad mediante
una referencia fuerte. Los entornos viven en el heap y se liberan con ARC; una closure no
retiene un frame de stack.

En W0, `pub` controla las exportaciones y `import "archivo.w" as nombre` permite nombres
calificados. La FFI `extern "C"` acepta escalares de ancho definido y handles `opaque`;
W no cede su allocator al código C. Las clases e interfaces genéricas se especializan en
W0. La stdlib incluye `std/io`, `std/text`, `std/bytes` y `std/algorithms`. `./w lsp`
reutiliza el checker y los spans del lexer.

La cobertura del corpus principal se mide por separado en la [matriz de
paridad](ENGINE_PARITY_MATRIX.md): contiene 121 fixtures y no incluye los contratos de
expansión de `tests/unit/test_expansion_contracts.py`. F01 cerró la paridad de ese corpus,
incluidos los genéricos y el fixture de módulos comprobados. Una suite E en verde no
significa que cada caso pase en todos los motores; los motores concretos se declaran en
ese test.
