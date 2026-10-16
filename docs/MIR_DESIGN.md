# MIR de W: contrato ejecutable

El backend principal sigue esta ruta: AST comprobado → HIR verificado → MIR verificado
→ C99 → compilador del sistema. `w emit-c` y `w build` la usan por defecto; el nombre
CLI `--backend=hir` se conserva por compatibilidad. `--backend=ast` y W1 son emisores
independientes. `w mir archivo.w` imprime el MIR en JSON después de verificarlo.

## Representación

`mir/Nodes.py` define módulos, funciones, slots tipados, layouts físicos, operaciones,
bloques básicos y terminadores `goto`, `branch`, `return`, `unreachable`. Es una IR de
slots mutables, **no SSA**. Sus operandos son identidades y proyecciones resueltas, no
nodos AST/HIR ni fragmentos C. Cada operación conserva su ubicación de fuente.

Los campos incluyen offsets sobre el layout completo, incluida la herencia. Las rutas
mutables capturan índices e identidad de clase antes del RHS y resuelven el slot después;
no guardan punteros a elementos que una realocación pueda invalidar. Los patrones se
convierten en predicados y ramas; el narrowing de una unión de errores necesita una
prueba exitosa que domine su uso.

## Efectos y propiedad

`clone` retiene; `store` mueve; `release` libera. Constructores, llamadas, lecturas,
escrituras y checks tienen categorías de efectos explícitas. Las llamadas declaran sus
operandos consumidos. Los parámetros administrados son prestados; los resultados son
propios. La bajada inserta cleanup LIFO en salidas normales, retornos, propagación,
break y continue. Los valores que escapan se protegen antes del cleanup.

`mir/Verifier.py` comprueba identidades, arena de tipos, firmas, offsets, almacenamiento,
aridad, efectos y sucesores. El análisis de datos intersecta inicialización definida y
une referencias posiblemente vivas en joins y backedges; rechaza lecturas consumidas,
movimientos de préstamos y retornos con referencias propias pendientes. No demuestra
la corrección de los helpers C ni controla los handles externos `opaque`.

## Almacenamiento y ABI

Locales, parámetros y retornos `int`, `float` y `bool` usan `int64_t`, `double` y `bool`.
Los contadores y predicados internos también son escalares. Globales, strings, listas,
tuplas, structs, objetos, opcionales y resultados siguen usando `WVal`. Adaptadores
convierten en fronteras de funciones como valores, closures y despacho virtual; la ABI
pública de los helpers y de FFI sigue siendo `WVal`.

No hay listas especializadas ni layouts de payload desempaquetados. El valor etiquetado
mide 48 bytes en la ABI arm64 medida; convertir un escalar en elemento vuelve a empaquetarlo.
La clasificación de efectos es conservadora, no un análisis interprocedural de pureza.

## Rangos

`for item in start..end` y `..=` capturan los límites una vez, de izquierda a derecha,
validan el tamaño y usan un contador sin crear una lista. Se conserva el límite de
100 millones de elementos aunque el cuerpo ejecute `break` inmediatamente. Un extremo
inclusivo `INT64_MAX` conserva el error existente. Los rangos usados como valores siguen
siendo listas con semántica CoW; no se introduce un tipo range nuevo.

W1 reconoce rangos directos en su parser; una expresión de rango envuelta en paréntesis
puede seguir la ruta materializada. La semántica pública es la misma; la optimización
sintáctica no es uniforme en todas las formas equivalentes.

## Evidencia y límites

`tests/unit/test_mir.py` altera MIR correcto para probar rechazo de CFG, referencias,
layout, almacenamiento, firma runtime, efectos y pruebas de narrowing inválidos.
Tres fixtures prueban límites, overflow y un rango de 100 millones con salida inmediata
en los cuatro motores. El bootstrap compara C0, C1 y C2; CI incluye GCC/Clang en Linux,
Clang en macOS y ASan/UBSan, con LSan en Linux.

La primera implementación MIR de ADR-018 registró, para 10.000 filas y cinco muestras
calientes con Clang `-O2` en arm64, 62,651 ms y 2,297 MiB para el backend MIR; C independiente da 8,182 ms y 2,078 MiB.
La fase anterior midió 87,776 ms y 27,109 MiB con tres muestras: aproximadamente 29 %
menos tiempo y 91,5 % menos RSS. Son ejecuciones distintas; no atribuyen cada mejora a
un cambio aislado ni representan todos los programas W. El binario MIR mide 99.568 bytes
frente a 37.120 en C. En esa ejecución, la diferencia de tiempo fue 7,7×.

La evidencia está en `docs/evidence/mir-2026-10-16/`. El siguiente trabajo debe perfilar
parsing, strings y fronteras runtime/FFI antes de decidir especializar contenedores.
LLVM sigue sin una justificación medida: el MIR habilita un experimento futuro, pero
cambiar el emitter no elimina los costes de representación y de los helpers.

## Cierre posterior (ADR-019)

El perfil de buffers identifica asignaciones por caracteres ASCII. Indexación y chr
reutilizan 128 strings estáticos inmutables, incluido NUL; Unicode conserva ownership.
10.000 filas y cinco muestras calientes, sin suites concurrentes: MIR 41,972 ms y
2,250 MiB; C 7,539 ms y 2,078 MiB. La ejecución previa con el mismo runner midió MIR
63,305 ms. Los buffers administrados bajan de 526.688 a 60.007 (88,6 %); no son
contadores de todos los malloc. El tiempo baja aproximadamente 33,7 %, pero C también
varía entre corridas; no atribuir una diferencia temporal exacta a un cambio aislado.
La diferencia residual de tiempo es 5,57×.

El tokenizer mide 23,026/44,388/86,232 ms para 52/104/208 KB; duplicar entrada en ese
tramo cuesta aproximadamente 1,93–1,94×. Las entradas pequeñas incluyen un coste fijo
de proceso. Evidencia: `docs/evidence/audit-completion-2026-10-16/`.

También se corrige el tail Result[unit, E]: MIR debe conservar Err, mientras que el
tail implícito de una función unit se evalúa y descarta. El fixture unit_tail_values
verifica ese límite junto a funciones, métodos, closures, opcionales y cleanup.
