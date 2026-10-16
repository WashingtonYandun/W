# Roadmap actual de W

Revisado: 2026-10-15. Este documento separa los hitos terminados de los límites que
siguen abiertos. La matriz y las suites automatizadas son la evidencia; un hito no se
considera cerrado solo porque su informe histórico diga que terminó.

## Estado

| Etapa | Estado | Alcance verificable |
| :--- | :--- | :--- |
| A–D | Cerradas | Estabilización, ownership, HIR, especialización genérica en W0, self-hosting y contratos de paridad documentados en `docs/history/`. |
| E01–E04 | Integradas | Funciones como valores, closures, módulos/FFI, OOP genérico, stdlib y LSP; la cobertura por backend está desglosada en [EXPANSION.md](EXPANSION.md). |
| F01 | Pendiente | Cerrar las 16 exclusiones actuales de W1 en el corpus público: 15 fixtures de genéricos y 1 fixture de módulos comprobados. |

“E integrada” no significa paridad universal entre motores. W0 tiene cobertura de la
expansión más amplia; W1 soporta subconjuntos medidos por fixture. La tabla del corpus
principal está en [ENGINE_PARITY_MATRIX.md](ENGINE_PARITY_MATRIX.md).

## F01 — Paridad de W1 en el corpus principal

### Alcance

W1 debe aceptar, compilar y ejecutar los fixtures genéricos válidos; rechazar los casos
inválidos con diagnóstico estable; y compilar el fixture `checked_modules`, que combina
imports y especialización genérica. La expansión actual de módulos de W1 puede conservarse
si resuelve correctamente el contrato; no se exige copiar la arquitectura interna de
`CompilationSession` de W0 por sí misma.

### Criterios de cierre

1. Los 114 fixtures del corpus pasan en los cuatro motores, incluidos los 16 actualmente
   excluidos para W1.
2. `python3 tools/ci_conformance.py --profile=release` pasa sin excepciones por motor.
3. Se mantienen el bootstrap de tres etapas, las salidas C deterministas y los diagnósticos
   de errores genéricos ya cubiertos por el corpus.
4. `tests/engine_profiles.json`, la matriz generada y esta documentación no declaran
   limitaciones de W1 para esos fixtures.

### Orden recomendado

1. Añadir tipos genéricos canónicos y sustitución de parámetros en el checker de W1.
2. Especializar funciones, structs y enums; deduplicar instancias y detectar layouts
   infinitos y crecimiento recursivo antes de emitir C.
3. Aplicar especialización a funciones y tipos importados y preservar identidad de módulo.
4. Habilitar los 16 fixtures en W1 y cerrar con bootstrap, integración, sanitizadores y
   perfil release.

Cada paso debe conservar una regresión pequeña antes de ampliar el siguiente. No se debe
quitar una exclusión de `engine_profiles.json` antes de que su fixture pase directamente
con el binario W1.

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
