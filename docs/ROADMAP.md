# Roadmap actual de W

Revisado: 2026-10-15. Este documento separa los hitos terminados de los límites que
siguen abiertos. La matriz y las suites automatizadas son la evidencia; un hito no se
considera cerrado solo porque su informe histórico diga que terminó.

## Estado

| Etapa | Estado | Alcance verificable |
| :--- | :--- | :--- |
| A–D | Cerradas | Estabilización, ownership, HIR, especialización genérica en W0, self-hosting y contratos de paridad documentados en `docs/history/`. |
| E01–E04 | Integradas | Funciones como valores, closures, módulos/FFI, OOP genérico, stdlib y LSP; la cobertura por backend está desglosada en [EXPANSION.md](EXPANSION.md). |
| F01 | Cerrada | Los 114 fixtures pasan en los cuatro motores; W1 incluye los 15 casos genéricos y el fixture de módulos comprobados. |
| F02 | Cerrada | Panics operativos nativos `W4001`/`W4002` con ubicación exacta en AST C99, HIR C99 y W1; política de ciclos ARC y `W_MEM_CHECK` opt-in fijada en ADR-012. |
| F03 | Cerrada | Uniones cerradas en el canal de error, propagación por subconjunto y patrones exhaustivos en los cuatro motores; ADR-013. Release 121/121, bootstrap fijo y ASan/UBSan limpios. |

“E integrada” no significa paridad universal entre motores. W0 tiene cobertura de la
expansión más amplia; W1 soporta subconjuntos medidos por fixture. La tabla del corpus
principal está en [ENGINE_PARITY_MATRIX.md](ENGINE_PARITY_MATRIX.md).

## F01 — Paridad de W1 en el corpus principal

### Resultado verificado

W1 acepta, compila y ejecuta los fixtures genéricos válidos, rechaza los casos inválidos
con sus diagnósticos esperados y compila `checked_modules`, que combina imports y
especialización genérica. Conserva su frontend de expansión de módulos; F01 exigía el
comportamiento observable del corpus, no replicar `CompilationSession` de W0.

### Criterios cumplidos

1. `python3 tools/ci_conformance.py --profile=release`: 114/114 en intérprete, AST C99,
   HIR C99 y W1; cero fallos y cero exclusiones.
2. El bootstrap compila las tres etapas y verifica hashes idénticos de `compiler0.c`,
   `compiler1.c` y `compiler2.c`.
3. `tests/engine_profiles.json` no declara exclusiones para estos fixtures y los casos
   inválidos conservan diagnósticos comprobados.

La cobertura es la del corpus finito, no una promesa de paridad para todo programa W ni
para toda la suite E. La diferencia arquitectónica entre la expansión tokenizada de W1 y
las sesiones tipadas de W0 también se mantiene; véase [ENGINE_PARITY_MATRIX.md](ENGINE_PARITY_MATRIX.md).

La integración se protege con regresiones directas de W1 en
`tests/unit/test_w1_generic_functions.py`, el perfil release y la suite de bootstrap.

## F02 — Diagnósticos nativos y política ARC

Los backends AST C99, HIR C99 y W1 reportan ruta, línea y columna para división/módulo
por cero, fallos de indexación y `list.pop()` sobre listas vacías. La regresión
`tests/unit/test_runtime_source_locations.py` exige el mismo formato y ubicación en los
tres backends.

El runtime no recolecta ciclos ARC. `Weak[C]` sigue siendo el mecanismo explícito para
romper ciclos; `W_MEM_CHECK=1` es una verificación opt-in de contadores lógicos durante
la salida normal y no cambia el comportamiento de producción si no se solicita. ADR-012
registra este contrato y sus límites.

Los detalles no cubiertos —sobre todo ubicaciones para fallos internos `W4003` y para
fallos de runtime fuera del conjunto operacional anterior— permanecen en
[KNOWN_LIMITS.md](KNOWN_LIMITS.md).

## F03 — Uniones cerradas de errores

F03 permite declarar distintos tipos de error en `T ! E1 | E2`. `?` propaga cuando el
conjunto de errores de origen está contenido en el conjunto destino, sin convertir ni
envolver de nuevo el payload. `else err` conserva el valor original y `match` exige cubrir
cada alternativa cuando produce un valor.

El contrato inicial limita las alternativas a `int`, `float`, `bool`, `str`, `struct` no
genéricos y `enum` no genéricos. Los patrones `Tipo(error)` y `Tipo(_)` comprueban la
identidad runtime del payload. Clases, genéricos y tipos compuestos quedan fuera hasta que
tengan una identidad runtime inequívoca.

F03 quedó cerrada con pruebas de interning y subconjuntos; casos válidos e inválidos en
los cuatro motores; matriz de paridad actualizada; release 121/121 sin exclusiones;
bootstrap de tres etapas con hashes idénticos; 55/55 programas runtime en la etapa 2; y
ASan/UBSan más `W_MEM_CHECK` limpios para el fixture de composición.

## Después de F03

Las capturas mutables y la concurrencia cambian semántica y modelo de memoria; siguen
diferidas hasta contar con casos de uso y contratos separados. La expansión de W1 más allá
del corpus principal —por ejemplo, FFI o todos los contratos de closures y OOP genérico—
requiere una decisión posterior basada en uso y coste.
