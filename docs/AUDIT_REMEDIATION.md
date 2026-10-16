# Implementación de la auditoría de main

> Informe de la primera fase. ADR-018 y [MIR_DESIGN.md](MIR_DESIGN.md) actualizan
> el estado de MIR, rangos, ABI escalar y mediciones; los resultados siguientes son históricos.

Base: `ebe2aa38ceb7e092244c53740b7a2eb545314b0d`. Rama:
`feat/audit-remediation-2026-10-16`. Decisiones: [ADR-017](adr/ADR-017-audit-remediation-and-backend-gates.md).

## Qué se corrigió

- **A01 — Confusión de tipos en métodos.** HIR distingue intrínsecos de colección y
  llamadas virtuales. Verifica receptor, firma, clase y slot canónico; el emitter consume
  el slot. El runtime comprueba tags antes de desreferenciar colecciones mutables.
- **A02/A03 — Retornos e inicialización falsamente completos.** Cobertura de patrones
  extraída a un módulo puro; análisis composicional de salidas compartido por AST/HIR.
  Un match parcial conserva su ruta sin coincidencia. El verificador revisa también
  funciones sin tail. Constructores incluyen esa ruta al intersectar campos inicializados.
- **A04 — Efectos repetidos y valor de asignación inconsistente.** `HirAssignment`
  representa la expresión, preserva el valor, captura índices/receptores una vez y resuelve
  slots después del RHS. AST y W1 devuelven el valor asignado en destinos compuestos.
  Se elimina el límite artificial a dos niveles de asignación.
- **A05 — Layout dependiente del orden escrito.** Los valores se evalúan en orden fuente
  y se almacenan en orden de declaración. La igualdad estructural no depende de permutar
  campos nombrados.
- **A06/A07 — Capturas y nombres resueltos otra vez por texto.** Capturas por identidad
  del símbolo; bindings de `else` y patrones de tipo locales. Las variables prevalecen
  sobre variantes, builtins y plantillas genéricas homónimas. Los inicializadores locales
  se materializan antes de declarar la variable C que los podría sombrear.
- **A08/A09 — Diferencias del intérprete.** Snapshots de operandos, argumentos y literales;
  receptor de clase de una mutación fijado antes de argumentos. `read_file` conserva CRLF
  y NUL. Conversiones float con gramática ASCII común; bool numérico, `len(tuple)` y
  `str` de compuestos cumplen SPEC. Rangos inválidos comparten límites con C.
- **A10 — Costes cuadráticos medidos.** Longitud de strings con ownership cacheada,
  independiente del índice UTF-8 lazy; `join_strings` de dos pasadas. `text.join`,
  `pad_left` y `bytes.decode` evitan concatenar acumuladores crecientes.
- **A11/A12 — Cobertura y afirmaciones sin soporte.** 28 casos permanentes de regresión y
  control, propiedades con oráculo de salida independiente, reducción que conserva los
  motores del fallo y presupuestos de ejecución acotados. CI y `./w test` incluyen los
  contratos nuevos. SPEC, estado experimental, matriz y límites se actualizan. La caché
  de bootstrap incorpora los módulos semánticos extraídos y dependencias del frontend.

## Evidencia automática

- `python3 -m pytest -q`: **77 pruebas**.
- `python3 tools/ci_conformance.py --profile=release --sanitize`: **158/158 fixtures en
  intérprete, AST C99, HIR C99 y W1 directo**; cero exclusiones. 134 core, 15 genéricos,
  1 módulos comprobados y 8 uniones de error.
- `./w test`: **633/633 comprobaciones**, incluido bootstrap de tres etapas con C idéntico.
- `W_SANITIZE=1 python3 -m tests.unit.test_audit_remediation`: ocho seeds con salida
  independiente; mezclan permutación de campos, scopes, variantes/builtins/plantillas
  sombreadas, métodos llamados como intrínsecos, cadenas de asignación y snapshots.
- El verificador recibe HIR manipulado: destino no direccionable, clase tratada como
  lista, slot falso y función por valor con fallthrough unit. Rechaza antes de emitir C.
- SQLite: referencia C, AST, HIR y W1 directo verifican importación atómica, segunda
  ejecución persistente y 14 fallos; cero handles vivos y cero stderr de ASan/UBSan.
  En macOS no hay LSan. Los gates Linux de CI activan LSan; no se han ejecutado localmente.

Los totales no significan cobertura exhaustiva ni ausencia de otros bugs. Los fixtures
invalidan aceptación incorrecta: concordar en aceptar un programa inválido no cuenta
como éxito. El bootstrap prueba convergencia, no solidez semántica.

## Flujo útil: mediciones CSV → SQLite

[import_csv.w](../examples/ffi/sqlite/import_csv.w) lee un archivo de usuario, valida
enteros no negativos de 64 bits, rechaza duplicados y conserva las filas anteriores ante
cualquier error del lote. El helper que abre el handle también lo destruye. El adaptador
sigue siendo obligatorio: esta FFI no transporta strings ni comprueba ownership `opaque`.

[FFI_VALIDATION.md](FFI_VALIDATION.md) fija formato, comandos y límites. Los datos de las
pruebas son generados; aún falta medir ahorro de trabajo con un archivo operativo real.

## Medición local reproducible

Apple Silicon arm64, macOS, Apple Clang 21, C99 `-O2 -g`, SQLite 3.51.0. 10000 filas,
enteros superiores a 32 bits, CRLF; tres muestras tras descartar una de calentamiento.
Cada muestra usa una base nueva. El tiempo incluye inicio de proceso, validación e I/O.
La compilación compartida del adaptador queda fuera; el bootstrap W1 se mide aparte.

- **C:** construcción 0,170 s; ejecución mediana **9,355 ms**; pico RSS mediano **2,08 MiB**;
  binario **37120 bytes**.
- **AST C99:** construcción 0,700 s; ejecución **91,066 ms**; RSS **26,94 MiB**;
  binario **100432 bytes**.
- **HIR C99:** construcción 0,630 s; ejecución **87,776 ms**; RSS **27,11 MiB**;
  binario **100432 bytes**.
- **W1 directo:** construcción 1,159 s; ejecución **88,221 ms**; RSS **27,08 MiB**;
  binario **100432 bytes**. Bootstrap separado: 21,567 s en esa ejecución.

**W es unas nueve veces más lento en este flujo y consume unas trece veces más RSS que
C.** Es un resultado mediocre de rendimiento. La integración funciona; la representación
etiquetada y los rangos materializados todavía cuestan demasiado. El dato no demuestra
que otro emitter resuelva el problema. RSS es un máximo por proceso aislado; no un conteo
lógico de asignaciones ni una medición de heap solamente.

El lexer W1 sin modificar procesaba 52 KB en **938,62 ms** sobre main y ahora en
**27,63 ms**, unas 34 veces menos. Con 104/208 KB mide 53,18/107,19 ms: el escalado pasó
de cerca de cuadrático a aproximadamente lineal para este corpus. Las muestras de 6,5/13
KB están dominadas por inicio de proceso. No extrapolar el factor a todo el compilador.

Los JSON con muestras y comandos están en [evidence/audit-remediation-2026-10-16](evidence/audit-remediation-2026-10-16).
Los paths de checkout se sustituyen por `<checkout>`; los binarios temporales desaparecen
al terminar. Reproducir con `tools/validate_sqlite_import.py` y `tools/measure_tokenizer.py`.

## Qué queda y por qué

1. **C99 sigue siendo el backend.** LLVM queda condicionado a un bloqueo medido, una IR
   compartida de efectos/ownership y comparación con el mismo layout y checks.
2. **No hay MIR completo.** Esta rama añade contratos explícitos de llamadas, asignación
   y salidas. Bloques básicos, terminadores y ownership completamente bajado son otra fase.
3. **No se introducen rangos lazy ni unboxing.** Los rangos conservan semántica list[int]
   y `WVal` conserva 48 bytes en la ABI medida. El perfil del importador justifica evaluar
   un lowering especial de `for` sobre rango antes de una migración de backend.
4. **No se añade defer/with.** El flujo actual obtiene cleanup único con un helper. Proponer
   sintaxis de recursos cuando otro flujo demuestre que ese patrón no basta.
5. **Ciclos ARC, concurrencia, capturas mutables y Windows siguen separados.** Resolver
   estos defectos no establece contratos nuevos de memoria ni promete producción segura.
