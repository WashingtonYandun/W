# Validación de W para integrar bibliotecas C

- **Estado:** Piloto técnico y flujo CSV → SQLite implementados; perfil de producción pendiente.
- **Fecha:** 2026-10-16

## Flujo elegido

Washington delegó elegir una prueba útil. `examples/ffi/sqlite/import_csv.w` importa
mediciones a una base local persistente: valida columnas, enteros ASCII de 64 bits y
límites; usa una transacción; devuelve errores de datos o SQLite; destruye sus recursos.
`import_reference.c` implementa el mismo contrato de forma independiente, con el mismo
adaptador C y biblioteca. No disponemos todavía de un archivo operativo del usuario ni
una medición del tiempo que le ahorra: eso sigue siendo la validación de producto.

El formato admite exactamente el encabezado `id,value` y hasta 100000 filas. Ambas
columnas son enteros decimales no negativos en `[0, INT64_MAX]`. Admite LF, CRLF y última
línea sin salto; no admite comillas, campos vacíos, signos, cifras Unicode, NUL ni columnas
adicionales. No es un parser CSV general. El identificador es clave primaria: duplicados
en el lote o en la base abortan todo el lote. La suma total también debe caber en int64;
se consulta antes de confirmar, y un overflow SQLite revierte la importación.

Una importación válida persiste datos; una inválida conserva exactamente las filas
anteriores. Los errores de datos/SQLite devuelven estado 1; uso o lectura, estado 2;
éxito, estado 0. `--version` muestra la versión SQLite enlazada.

## Ownership y coste del adaptador

La FFI transporta escalares y `opaque`; no strings ni buffers W. La ruta de la base entra
por `W_SQLITE_DB`. `adapter.c` mantiene SQL fijo, conexión y sentencias preparadas; el
adaptador es código de producto que hay que mantener. Cierra sentencias y conexión con
`pilot_close`, y libera el control con `pilot_dispose`. Cierre repetido es válido; uso
tras cierre devuelve `SQLITE_MISUSE`. Usar un handle tras destruirlo o destruirlo dos
veces sigue siendo un error inseguro que W no impide.

El helper W que adquiere el recurso reúne las salidas posteriores a la adquisición en
un único punto de destrucción. Los errores retornados por `populate` se manejan antes de
salir. No hace falta introducir `defer/with` para este caso; ADR-017 registra la decisión.
Los contadores externos comprueban conexión, control y sentencias vivos. `W_MEM_CHECK`
solo comprueba asignaciones W en salida normal; `exit()` no ejecuta ese chequeo. Los
sanitizers y el contador externo son necesarios en este CLI, que devuelve códigos de salida.

## Reproducir

Se necesitan un compilador C99, cabeceras SQLite y `libsqlite3`. Linux CI instala
`libsqlite3-dev`; macOS usa el SDK y la biblioteca del sistema.

```sh
python3 tools/validate_sqlite_ffi.py --sanitize
python3 tools/validate_sqlite_import.py --sanitize --rows 1000 --samples 1
python3 tools/validate_sqlite_import.py --rows 10000 --samples 3 --report .w_cache/sqlite-import/optimized.json
python3 tools/measure_tokenizer.py
```

Para usar el importador desde la raíz del repositorio:

```sh
mkdir -p .w_cache/sqlite-import
cc -std=c99 -O2 -c examples/ffi/sqlite/adapter.c -o .w_cache/sqlite-import/adapter.o
./w build examples/ffi/sqlite/import_csv.w --link-lib .w_cache/sqlite-import/adapter.o --link-lib sqlite3 -o .w_cache/sqlite-import/import_csv
W_SQLITE_DB=.w_cache/sqlite-import/measurements.sqlite .w_cache/sqlite-import/import_csv measurements.csv
```

El runner verifica C/AST/HIR y W1 invocado directamente, sin checker W0 previo para el
input. Una conexión Python independiente compara las filas persistidas, no solo la salida.
Prueba append en una segunda ejecución y 14 fallos, incluido un error después de insertar
una primera fila válida. Exige rollback, código de salida, cero recursos externos vivos
y cero stderr de sanitizers. Linux activa LSan; macOS no lo soporta. SQLite del sistema
no se recompila instrumentado. El piloto anterior `measurements.w` conserva su prueba
C/AST/HIR de cierre repetido y uso tras cierre.

## Medición e interpretación

Cada JSON registra compilador, plataforma, versión SQLite enlazada, flags, comandos,
tiempo de construir cada programa, muestras, tamaño del binario y pico de memoria física.
La compilación compartida del adaptador queda fuera del tiempo de cada programa; el
bootstrap W1 se informa aparte. Se descarta una ejecución de calentamiento.

`tools/measure_process.py` ejecuta exactamente un hijo en un proceso de medición nuevo:
`ru_maxrss` no hereda máximos de ejecuciones anteriores. Darwin informa bytes y Linux
KiB, convertidos a bytes. El tiempo incluye inicio del binario, SQLite e I/O; excluye
el lanzamiento del helper Python. RSS y tamaño dependen de plataforma, flags y SDK.
Estos valores describen el flujo completo, no el coste aislado de FFI.

W ofrece errores tipados y control del flujo en el lenguaje; aún necesita un adaptador
manual y tiene costes de representación altos frente a C. El resultado valida utilidad
técnica concreta, no una ventaja general de rendimiento ni un perfil de producción.
