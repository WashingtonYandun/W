# ADR-019 · Cierre de auditoría con oráculos y asignaciones medidas

- **Estado:** Aceptada
- **Fecha:** 2026-10-16
- **Extiende:** ADR-017 y ADR-018

## Decisión

Conservar la sintaxis y las reglas publicadas. El tail implícito de una función unit se
evalúa por sus efectos y se descarta; los returns explícitos conservan comprobación de
tipo. Result[unit, E] mantiene sus errores. W1 distingue bare return por token, no por
línea, y valida match desde su parser semántico, sin un scanner de llaves paralelo.

Ampliar el gate del formatter a fuentes de producción: equivalencia estructural del AST
sin spans e idempotencia. Los árboles tipados recursivos tienen un modelo independiente
de valores, scopes y secuencia de efectos; se ejecutan tanto originales como formateados.
La concordancia entre motores no basta si comparten un bug del runtime.

Reutilizar strings ASCII de un carácter con almacenamiento estático inmutable. NUL tiene
longitud uno y terminador independiente. Indexación y chr evitan buffers propios para
este dominio; Unicode restante conserva su representación administrada. No se introducen
views ni cambios en WVal. Retener o liberar un string estático sigue siendo un no-op.

Recoger W_MEM_STATS en una ejecución separada de las muestras temporizadas de SQLite.
Son contadores de buffers administrados, no de todos los malloc ni bytes de heap. C no
produce esos contadores; el reporte usa null, sin fingir una medida igual a cero.

## Evidencia y consecuencias

La medición previa del importador de 10.000 filas registra 526.688 buffers administrados.
La reutilización ASCII reduce ese número a 60.007, sin handles vivos ni pérdida de
persistencia/rollback. El test de runtime exige cero asignaciones para los 128 chr ASCII
con clones/releases y comprueba que indexación sobre un owner destruido sigue válida.
NUL, Unicode, snapshots y strings retornados se ejecutan en los cuatro motores.

AUDIT_STATUS.md gobierna el seguimiento vigente de A01–A12. Los informes históricos se
conservan. No se adopta LLVM, un collector de ciclos, concurrencia ni un nuevo modelo de
capturas/recursos; ninguno tiene un requisito de producto demostrado en esta fase.
