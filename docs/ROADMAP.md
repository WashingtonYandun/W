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

## Después de F01

Antes de añadir más sintaxis, resolver dos límites operativos ya documentados en
[KNOWN_LIMITS.md](KNOWN_LIMITS.md): ubicaciones de origen en panics de binarios nativos y
política explícita de reporte de ciclos ARC. El reporte de memoria debe seguir siendo
opt-in hasta decidir cómo distinguir errores de desarrollo de ejecuciones de producción.

Las capturas mutables, las uniones de errores y la concurrencia cambian semántica y modelo
de memoria. Quedan diferidas hasta que existan casos de uso concretos y contratos separados;
no se mezclan con F01 ni se anuncian como parte de E01–E04.

La expansión de W1 más allá del corpus principal —por ejemplo, FFI o todos los contratos
de closures y OOP genérico— necesita una decisión posterior basada en uso y coste. F01 no
la promete.
