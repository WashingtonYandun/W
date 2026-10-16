# ADR-012 · Diagnósticos nativos y política de ciclos ARC

- **Estado:** Aceptada
- **Fecha:** 2026-10-15
- **Etapa:** F02

## Contexto

Los panics de W en binarios C99 terminaban dentro de `runtime/w_runtime.h`, que no
conocía el span de la operación W que los provocó. Por separado, el runtime usa ARC y
no recolecta ciclos fuertes. `W_MEM_CHECK=1` ya permitía detectar ciertos ciclos al salir,
pero el repositorio no fijaba si ese reporte debía estar activo en producción.

## Decisiones

1. **Ubicación en el runtime.** Los emisores AST C99, HIR C99 y W1 adjuntan ruta, línea y
   columna directamente a las operaciones que pueden producir los panics operacionales
   cubiertos: división/módulo por cero, lecturas inválidas de índices, escritura de un
   índice de lista fuera de rango y `list.pop()` sobre lista vacía. El runtime conserva
   `[Wxxxx] RuntimeError: ...` como fallback cuando no recibe un span.
2. **Alcance honesto.** No se atribuyen ubicaciones de usuario a fallos internos de
   invariantes de memoria/tipos (`W4003`) ni a llamadas del runtime fuera de las
   operaciones enumeradas. Esos sitios pueden no tener un origen W único.
3. **Ciclos ARC.** ARC no recolecta ciclos fuertes. Los programas deben usar `Weak[C]`
   para relaciones de vuelta cuando quieran liberar el grafo de forma determinista.
4. **Reporte de memoria.** `W_MEM_CHECK=1` permanece opt-in. Revisa contadores lógicos de
   buffers W durante cleanup normal; no recolecta ciclos, no se ejecuta tras un `exit()`
   por panic y no reemplaza ASan/LSan en desarrollo/CI. Sin la variable, un ciclo fuerte
   no altera stderr ni el código de salida.

## Consecuencias

- Los errores de runtime más comunes son accionables en los tres emisores nativos y se
  pueden comparar con el diagnóstico del intérprete.
- Hay un estado global de ubicación en el runtime C. W no ofrece concurrencia en este
  hito; si el runtime pasa a permitir llamadas paralelas, el estado deberá hacerse local
  al hilo o transportarse como contexto explícito.
- La suite mantiene una prueba positiva de detección con `W_MEM_CHECK=1` y otra de
  silencio/éxito con la opción ausente. ASan/LSan siguen cubriendo fugas a nivel de bytes.

## Verificación

`tests/unit/test_runtime_source_locations.py` exige ubicaciones exactas para los panics
cubiertos en AST C99, HIR C99 y W1. `tests/unit/test_weak_references.py` valida los dos
modos de reporte de ciclos. El perfil release y el bootstrap verifican después la
integración con el corpus y el compilador autoalojado.
