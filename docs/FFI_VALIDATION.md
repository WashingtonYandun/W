# Validación de W para integrar bibliotecas C

- **Estado:** Piloto técnico SQLite implementado; ventaja de uso pendiente de validar.
- **Fecha:** 2026-10-16

## Hipótesis

W puede servir para construir herramientas nativas pequeñas que usan una biblioteca C
y expresan el flujo de aplicación, la gestión de errores y los datos en W. La utilidad
debe demostrarse con un flujo real. Emitir C99, superar el bootstrap o ejecutar `sqrt`
no demuestra por sí solo que W reduzca el coste de ese trabajo.

## Alcance del primer piloto

Washington delegó la elección de biblioteca. Se eligió **SQLite** para un registro
local de mediciones: insertar un lote en una transacción, consultar cantidad y total,
conservar la base en disco y manejar errores recuperables. Su interfaz C separa
conexiones y sentencias preparadas con ciclos de vida explícitos; véase la
[introducción oficial](https://www.sqlite.org/cintro.html).

`examples/ffi/sqlite/measurements.w` controla el lote, valida los datos y maneja
`DatabaseError | InputError`. `adapter.c` adapta los punteros de salida y las operaciones
SQL fijas a escalares y `opaque`, sin exponer buffers ni transferir asignaciones de W.
`reference.c` ejecuta el mismo flujo con el mismo adaptador y biblioteca.

El perfil usa W0 AST/HIR. W1 queda fuera del compromiso FFI hasta disponer de cobertura
propia. El adaptador no es un driver SQL general: la FFI actual no transporta strings,
callbacks ni buffers. La ruta se recibe mediante `W_SQLITE_DB` y el tamaño del lote
mediante `W_SQLITE_ROWS` (1..100000); por defecto se usan memoria y 1000 registros.

## Ownership del adaptador

`pilot_open` crea un control C, una conexión y una sentencia preparada. Incluso si
SQLite no abre la base, un control no nulo debe destruirse con `pilot_dispose`.
`pilot_close` finaliza la sentencia y cierra la conexión; conserva el control, admite
una segunda llamada y permite comprobar que una inserción posterior devuelve
`SQLITE_MISUSE`. `pilot_dispose` cierra los recursos restantes y libera el control.

Después de un `pilot_dispose` exitoso el handle deja de ser válido: no se debe copiar,
usar ni destruir otra vez. W no comprueba esa disciplina de punteros externos. El
contador del adaptador comprueba controles, conexiones y sentencias abiertos; el
runtime W no es dueño de esos recursos.

## Condiciones de aceptación

1. Programa reproducible desde un checkout limpio, con versión de biblioteca, flags de
   compilación/enlace e instrucciones de instalación registradas.
2. Misma salida y códigos de error que una implementación C de referencia del mismo
   flujo; incluir entrada válida, inválida y fallo de la biblioteca.
3. ABI comprobado en los compiladores/plataformas que se decida soportar. Probar los
   límites de conversión de `int32`, enteros de 64 bits y valores `double` utilizados.
4. Creación, uso y destrucción repetidos de recursos sin fallos de ASan/UBSan. En Linux,
   comprobar también LSan. `W_MEM_CHECK` comprueba las asignaciones de W y no sustituye
   la comprobación de recursos gestionados por la biblioteca C.
5. Medir tiempo de compilación, tiempo de ejecución, memoria y tamaño del binario contra
   la referencia C con igual carga, versión de biblioteca y flags. Registrar comandos,
   muestras y límites; no fijar cifras objetivo sin conocer el caso real.
6. Washington debe poder completar y mantener el flujo con una ventaja concreta: menos
   trabajo manual, errores más claros o integración más sencilla. Registrar también el
   código del adaptador necesario y las limitaciones encontradas.

## Reproducción y evidencia

Se requieren un compilador C99, cabeceras SQLite y `libsqlite3`. En Debian/Ubuntu se
instalan con `sudo apt-get install libsqlite3-dev`; en macOS se usan las cabeceras del
SDK y la biblioteca del sistema. CI instala la dependencia de Linux explícitamente.

```sh
python3 tools/validate_sqlite_ffi.py --sanitize --report .w_cache/sqlite-ffi/sanitized.json
python3 tools/validate_sqlite_ffi.py --rows 1000 --samples 3 --report .w_cache/sqlite-ffi/optimized.json
```

Para conservar un ejecutable y probar una base propia desde la raíz del repositorio:

```sh
mkdir -p .w_cache/sqlite-ffi
cc -std=c99 -O2 -c examples/ffi/sqlite/adapter.c -o .w_cache/sqlite-ffi/adapter.o
./w build examples/ffi/sqlite/measurements.w --link-lib .w_cache/sqlite-ffi/adapter.o --link-lib sqlite3 -o .w_cache/sqlite-ffi/measurements
W_SQLITE_DB=.w_cache/sqlite-ffi/measurements.sqlite W_SQLITE_ROWS=1000 .w_cache/sqlite-ffi/measurements
```

Usar una ruta nueva para cada lote independiente: una segunda ejecución sobre esa misma
base detecta los identificadores duplicados y conserva los registros existentes.

El runner compila C/AST/HIR, exige la misma salida y verifica la base persistida con una
conexión independiente. Comprueba valores de 64 bits, restricciones por duplicados,
entrada negativa, fallo de apertura, configuración inválida, cierre repetido y uso tras
cierre. Exige cero recursos vivos del adaptador y cero salida de sanitizers o
`W_MEM_CHECK`. Linux activa LSan; macOS no. La biblioteca SQLite del sistema no se
recompila con instrumentación; se instrumentan el adaptador y los programas del piloto.

Los JSON registran plataforma, compilador, versión SQLite, flags, comandos, tiempo de
construcción, muestras de ejecución y tamaño de binario. La compilación del adaptador
compartido se excluye del tiempo de construcción de cada programa. Se descarta una
ejecución de calentamiento y se informa la mediana. La medición incluye inicio del
proceso, SQLite e I/O; no aísla el coste de FFI. `peak_memory_bytes` queda en `null`:
todavía no se mide el pico de memoria física.

El piloto prueba integración técnica y ownership en este flujo. No demuestra ventaja
general de rendimiento ni utilidad para un usuario: el lote es sintético. El siguiente
paso de producto es sustituirlo por datos y un flujo real, medir memoria y mantenimiento
frente a C, y registrar una ventaja concreta antes de declarar un perfil de producción.
