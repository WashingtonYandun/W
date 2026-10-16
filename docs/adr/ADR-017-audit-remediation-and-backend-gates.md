# ADR-017 · Semántica verificable antes de cambiar de backend

- **Estado:** Aceptada
- **Fecha:** 2026-10-16
- **Base auditada:** `main` en `ebe2aa38ceb7e092244c53740b7a2eb545314b0d`

## Decisión

Conservar C99 y las reglas de superficie actuales. Corregir las discrepancias observables
antes de ampliar el lenguaje. No iniciar una migración LLVM ni añadir concurrencia,
capturas mutables o un recolector de ciclos en esta corrección.

1. `match` parcial sobre dominios abiertos sigue permitido como sentencia. Su ruta sin
   coincidencia continúa normalmente: nunca garantiza un retorno ni inicializa un campo.
   La cobertura de patrones vive en `checker/PatternCoverage.py`; las salidas normales,
   retornos, rupturas y continuaciones se componen en `common/ControlFlow.py`. ConstructorFlow
   usa la misma cobertura para incluir el estado de la ruta sin coincidencia.
2. Una asignación produce el valor asignado. Se admite anidamiento limitado por los
   límites generales del parser, sin el rechazo artificial a tres asignaciones. HIR tiene
   `HirAssignment`; el backend evalúa cada índice y receptor de clase una sola vez, antes
   del RHS, y resuelve la ubicación mutable después del RHS para evitar punteros a slots
   invalidados por una realocación. Los valores observados como operandos y argumentos
   son snapshots CoW; las clases conservan identidad.
3. Una operación de colección necesita `CollectionCallTarget` y un receptor compatible.
   Una llamada virtual lleva un slot canónico por nombre y aridad, que el verificador
   comprueba y el emitter consume. `super` mantiene despacho estático. El nombre de un
   método de usuario no lo convierte en un intrínseco.
4. Los campos se evalúan en el orden escrito y se almacenan en orden de declaración.
   Las capturas se identifican por el símbolo resuelto; los bindings de handlers y
   patrones de tipo de error pertenecen a su scope local.
5. Implementar los contratos ya publicados: `len(tuple)`, conversiones numéricas de bool
   y `str` de valores compuestos. `read_file` conserva CRLF y NUL. La conversión textual
   de float usa una gramática ASCII explícita en ambos runtimes.
6. Cachear longitud de strings con ownership y usar un builder de dos pasadas para
   `join_strings`. `text.join`, `pad_left` y `bytes.decode` dejan de copiar acumuladores
   crecientes. El índice UTF-8 sigue siendo lazy y consume memoria proporcional al texto.

## Validación de utilidad y recursos externos

Washington delegó la elección del flujo. El importador `examples/ffi/sqlite/import_csv.w`
lee un archivo suministrado por el usuario, comprueba el formato y los enteros de 64 bits,
importa una transacción completa y conserva la base anterior si falla cualquier fila,
una restricción o la suma SQLite. El helper que adquiere el handle también lo destruye
antes de devolver el código de salida. Los errores recuperables pasan por un único punto
de cleanup; no se usa `?` después de adquirir el handle fuera de ese perímetro.

Este flujo no necesita sintaxis nueva `defer/with`. W sigue sin comprobar el ownership de
`opaque`: el adaptador C es parte del producto y debe mantenerse. Un segundo caso con
múltiples recursos y salidas entrelazadas puede justificar una propuesta específica.

C, AST C99, HIR C99 y W1 directo ejecutan el mismo contrato y adaptador. El runner
comprueba la base con una conexión independiente y mide el pico físico por proceso.
Esta evidencia amplía el piloto de ADR-016; no declara paridad FFI universal de W1.
El CSV es deliberadamente de dos columnas sin comillas, no un parser RFC 4180.

## Consecuencias y gate para LLVM

Las correcciones consolidan contratos HIR y análisis de salidas; **no constituyen un MIR
completo con ownership, bloques básicos y terminadores explícitos**. Ese trabajo permanece
como siguiente paso arquitectónico, después de un bloqueo de producto medido.

Un backend LLVM experimental requiere: representaciones y efectos fijados en una IR
compartida; regresiones y propiedades independientes limpias; un workload que demuestre
que el C99 optimizado es el bloqueo; y comparación con idénticos checks, ABI y layouts.
Cambiar de emitter conservando `WVal` y rangos materializados no elimina sus costes.
Unboxing y rangos lazy necesitan sus propios contratos y mediciones antes de implementarse.
