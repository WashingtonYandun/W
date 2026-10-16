# ADR-016 · Piloto FFI con SQLite y ownership externo explícito

- **Estado:** Aceptada para el piloto; perfil general de producción pendiente
- **Fecha:** 2026-10-16

## Contexto y decisión

Washington eligió validar integración con C y delegó la elección de biblioteca. Se
selecciona SQLite para comprobar persistencia local, transacciones, consultas y errores
recuperables con una dependencia C concreta. La referencia de API es la
[documentación oficial](https://www.sqlite.org/cintro.html).

El piloto usa W0 AST/HIR con la FFI existente de escalares y `opaque`. Un adaptador C
pequeño fija las operaciones SQL y adapta los punteros de salida. W controla los datos,
el lote y `DatabaseError | InputError`. No se amplía el ABI con strings, buffers,
callbacks ni ownership automático, y no se declara soporte FFI de W1.

El control C sigue el ciclo `pilot_open` → operaciones → `pilot_close` →
`pilot_dispose`. Cerrar libera sentencias y conexión, conserva el control y permite
detectar uso tras cierre. Destruir libera el control y exige exactamente una llamada
exitosa; no puede volver a utilizarse el puntero. Los contadores externos y sanitizers
complementan `W_MEM_CHECK`, que no administra esos recursos.

## Evidencia y límites

`tools/validate_sqlite_ffi.py` compara C/AST/HIR con igual adaptador y biblioteca,
verifica los datos persistidos de forma independiente, ejercita fallos y escribe
mediciones reproducibles. CI ejecuta la comprobación con sanitizers en Linux/macOS.

La biblioteca del sistema no se recompila instrumentada. El lote es sintético y la
memoria física máxima aún no se mide. Superar el piloto demuestra este contrato
técnico; demostrar una ventaja para un usuario requiere un flujo y datos reales.
`docs/FFI_VALIDATION.md` conserva los comandos y condiciones de aceptación pendientes.

## Evolución posterior · ADR-017

El importador CSV amplía el piloto a entradas de usuario, rollback atómico y medición
física por proceso. Su runner verifica C/AST/HIR y W1 directo. El compromiso sigue limitado
a esos programas: no demuestra soporte universal de FFI en W1. Los límites de la evidencia
inicial de esta ADR son históricos; los resultados actuales están en `AUDIT_REMEDIATION.md`.
