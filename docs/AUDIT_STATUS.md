# Estado vigente de la auditoría de main

Base auditada: `ebe2aa3`, 2026-10-16. Implementación en
`feat/audit-remediation-2026-10-16`. El informe de `AUDIT_REMEDIATION.md` conserva la
primera fase; ADR-018 y ADR-019 amplían ese cierre. Esta página gobierna el seguimiento
actual; los números históricos no describen el corpus vigente.

## Hallazgos originales

- **A01 · Despacho inseguro: corregido.** Targets de colección y virtuales distintos,
  firmas y receptores verificados; MIR consume esas decisiones. Regresiones:
  `audit_class_append.w`, `audit_class_get.w`, `test_audit_remediation.py` y `test_mir.py`.
- **A02/A03 · Retornos y constructores incompletos: corregidos.** PatternCoverage y
  ControlFlow comparten exhaustividad y aristas sin coincidencia. El checker y el
  verificador rechazan fallthrough incompatible e inicialización parcial. Regresiones
  negativas `audit_match_*`, `audit_ctor_*` y contratos de CFG/propiedad MIR.
- **A04 · Destinos y receptores evaluados tarde o dos veces: corregido.** Índices e
  identidad se fijan antes del RHS; el slot mutable se resuelve después. Asignación como
  expresión preserva el resultado. Regresiones `audit_assignment_index_twice.w` y
  `audit_collection_method_receiver_effect.w`; propiedades de efectos y CoW.
- **A05 · Layout no canónico: corregido.** Evaluación fuente L→R y almacenamiento por
  declaración; MIR usa offsets físicos verificados. Regresiones
  `audit_struct_field_order.w` y `audit_struct_field_effect_order.w`.
- **A06/A07 · Capturas y nombres: corregidos en los casos auditados.** Bindings por
  identidad, scope de handlers y prioridad de variables sobre variantes/builtins.
  Regresiones `audit_closure_handler_shadow.w`, `audit_local_shadow.w`,
  `audit_enum_shadow.w`, `audit_param_shadow_builtin.w` y árboles tipados con scopes.
- **A08/A09 · Oráculo, I/O y conversiones: corregidos.** Snapshots, CRLF/NUL, gramática
  float común y firmas documentadas verificadas. Regresiones `audit_read_crlf.w`,
  `audit_bool_conversion.w`, `audit_float_unicode.w`, `audit_len_tuple.w` y
  `audit_str_struct.w`. El cierre adicional alinea tails unit y return multilínea.
- **A10 · Costes evitables: corregidos los algoritmos y asignaciones demostrados.**
  Longitud/offsets UTF-8 cacheados, builders de dos pasadas, rangos directos sin listas,
  ABI escalar en MIR y caracteres ASCII estáticos sin asignación. SQLite se compara
  contra C con tiempos, CPU, RSS y un perfil separado de buffers administrados.
  Esto no promete igualar C ni elimina el layout WVal de los contenedores.
- **A11 · Cobertura combinatoria: reforzada con oráculos independientes.** Repros
  permanentes, propiedades previas y árboles recursivos tipados que componen ramas,
  scopes, errores, índices, efectos y capturas. Se ejecutan antes y después del formato
  en los cuatro motores. Las pruebas mutan HIR/MIR y verifican rechazos. No se declara
  un porcentaje de cobertura ni una prueba de ausencia de otros bugs.
- **A12 · Contratos contradictorios: corregidos y bajo gates.** SPEC, versión
  experimental, seguridad, capacidades y corpus documentados. El formatter ahora
  preserva AST e idempotencia en fixtures, runtime, ejemplos recursivos, stdlib y
  selfhost. Los informes de fases anteriores están rotulados como históricos.

## Defectos adicionales encontrados por los nuevos gates

1. El formatter eliminaba guards de match. Ahora conserva la condición; el gate de AST
   detecta esa pérdida aunque el resultado sea idempotente.
2. W1 rechazaba patrones enteros negativos y algunos sujetos compuestos de match por
   un scanner previo de llaves. El parser semántico valida el arrow y el scanner
   redundante desaparece; un lookahead local conserva W0001 para un arrow ausente
   tras un patrón simple, antes de resolver un sujeto atómico desconocido.
3. W1 perdía el tipo común de if al usarlo como operando en un contexto descartado.
   Ahora conserva ese tipo; las ramas incompatibles siguen rechazadas cuando producen
   un valor. La forma formateada y la original se prueban con el mismo oráculo.
4. Intérprete, AST y W1 filtraban un tail no-unit desde una función declarada unit.
   Ahora se evalúa y descarta con cleanup. MIR además conserva Err en un tail
   `unit ! E`; no convierte errores en éxito. Un return explícito incompatible se rechaza.
5. W1 usaba el salto de línea para distinguir bare return. Ahora consulta el token
   siguiente, conforme a SPEC; expresiones multilínea conservan su valor y error.

Fixtures: `ascii_string_lifetime.w`, `signed_match_patterns.w`,
`match_composed_subject.w`, `unit_tail_values.w`, `multiline_return_contract.w`,
`match_guard_preservation.w`, `signed_pattern_type.w` y `unit_explicit_return.w`.
El gate ejecutable es `python3 -m tests.unit.test_audit_completion`; CI y `./w test`
lo incluyen. Linux añade LSan a los sanitizers.

## Evidencia del cierre

87 pytest, 712 checks y 168 fixtures por motor con ASan/UBSan, cero exclusiones. El
formatter verifica 117 fuentes. Ocho seeds recursivos se ejecutan originales/formateados
en cuatro motores; 64 seeds adicionales verifican forma y determinismo de generación.
Son comprobaciones finitas, no una tasa de cobertura.

SQLite, 10.000 filas y cinco muestras calientes: MIR 41,972 ms y 2,250 MiB; C 7,539 ms
y 2,078 MiB. Antes del pool ASCII: MIR 63,305 ms y 526.688 buffers; después: 60.007
buffers. El contador lógico se recoge fuera de las muestras temporizadas. C no dispone
de ese contador. La diferencia temporal residual es 5,57×.

Persistencia, rollback, 14 errores y cero handles se validan en C/AST/MIR/W1, también
con sanitizers. Los JSON reproducibles están en
[evidence/audit-completion-2026-10-16](evidence/audit-completion-2026-10-16/).

## Trabajo que requiere otra decisión

LLVM necesita demostrar un bloqueo de C99 con los mismos checks y representación.
Listas especializadas, ciclos ARC, concurrencia y capturas mutables cambian contratos
arquitectónicos y no son correcciones pendientes de A01–A12. Parser recovery, ampliación
LSP y compatibilidad Windows siguen como trabajo de ergonomía/plataforma separado.

El ownership de opaque sigue siendo manual. El importador usa un perímetro de cleanup
comprobado; esto no constituye seguridad FFI universal. Falta observar uso externo y
medir mantenimiento/productividad: una prueba sintética de SQLite no demuestra adopción.
Estos límites siguen publicados en KNOWN_LIMITS.md; cerrar hallazgos no los borra.
