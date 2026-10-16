# ADR-018 · MIR verificable, rangos directos y ABI escalar

- **Estado:** Aceptada
- **Fecha:** 2026-10-16
- **Extiende:** ADR-017

## Decisión

Sustituir la emisión directa desde HIR por una bajada a MIR de bloques básicos, slots
mutables y terminadores. El backend C99 consume solamente MIR verificado; la fachada
HIR conserva la selección CLI existente sin un fallback silencioso.

Resolver offsets físicos de campos, targets y operandos antes de emitir C. Representar
retención, transferencia, liberación y efectos explícitamente. Verificar inicialización,
consumo, cleanup y pruebas de narrowing sobre el CFG. No introducir SSA ni un optimizador
general para completar esta separación arquitectónica.

Eliminar la lista intermedia en los bucles directos sobre rangos en los cuatro motores.
Conservar evaluación única de límites, reglas de overflow y límite de tamaño existentes.
Los rangos usados como valores siguen materializados: no cambia la sintaxis ni el tipo.

Usar representación nativa para locales, parámetros y retornos primitivos del backend
principal. Conservar `WVal` para contenedores, globales y fronteras runtime/FFI; generar
adaptadores tipados en funciones como valores y dispatch virtual. Evitar la tabla de
índices UTF-8 cuando la longitud cacheada demuestra que el string es ASCII.

## Motivo y consecuencias

La medición del importador SQLite identificó presión de memoria por rangos y un coste
real de pasar todos los escalares en `WVal`. La primera emisión MIR sin ABI escalar fue
más lenta; la especialización forma parte de esta decisión, no una promesa posterior.
`MIR_DESIGN.md` registra los resultados y límites. Las listas siguen empaquetadas y W1
mantiene un emisor independiente; ninguno de esos costes desaparece por declarar MIR.

El verificador y los sanitizers cubren riesgos diferentes. CI debe validar el commit
nuevo en GCC/Clang sobre Linux/macOS y con LSan en Linux antes de integrar. El bootstrap
queda serializado por proceso para impedir reconstrucciones concurrentes del cache.

No adoptar LLVM todavía. Existe una IR que permite compararlo, pero falta demostrar
que el C99 optimizado, con las mismas reglas de seguridad y representación, es el bloqueo.
