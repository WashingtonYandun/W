# Documentación de W

- [Especificación del lenguaje](../SPEC.md): sintaxis y semántica públicas.
- [Diseño del MIR](MIR_DESIGN.md): CFG, ownership explícito, layouts y ABI escalar.
- [Diseño del HIR](HIR_DESIGN.md): representación intermedia y verificación.
- [Memoria y ownership](OWNERSHIP_LIFETIME.md): ARC, CoW y referencias débiles.
- [Paridad de motores](ENGINE_PARITY_MATRIX.md): capacidades y límites comprobados.
- [Expansión](EXPANSION.md): funciones como valores, closures, módulos públicos, FFI, OOP genérico, stdlib y LSP.
- [Roadmap actual](ROADMAP.md): estado comprobado, siguiente hito y criterios de cierre.
- [Decisiones técnicas](adr/): contratos de arquitectura versionados.
- [Correcciones de auditoría y evidencia](AUDIT_REMEDIATION.md): contratos corregidos, SQLite y mediciones contra C.
- `history/`: informes de hitos anteriores. Describen el estado de su fecha; no son la especificación vigente.

El repositorio contiene contratos técnicos y evidencia reproducible. Los registros personales de trabajo no forman parte de la documentación del lenguaje.
