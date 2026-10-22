# Registro de cambios

## 0.5.0 — preparado para release

### Lenguaje y compiladores

- Se consolida **Wysna** como identidad del lenguaje: se retiraron aliases de tokens y
  prefijos internos heredados de los nombres experimentales anteriores.
- Se añadieron separadores de sentencias por salto de línea y `;`. La regla cubre LF,
  CRLF y CR; los saltos dentro de paréntesis y corchetes continúan expresiones.
- Se unificó el manejo de signo menos: el lexer emite un operador unario y el parser
  reconoce el límite de `INT64_MIN`.
- Se alinearon el parser y el validador semántico del compilador autoalojado con los
  nuevos separadores y con los saltos antes de `else`/`elif` y manejadores `else err`.
- Se añadió una regresión de ejecución que verifica límites de sentencia, retorno,
  ramas, manejo de errores y listas multilínea.

### Documentación y alcance

- Se aclararon los roles de Wysna Seed y Wysna Compiler. Seed sigue siendo la tubería
  de referencia AST/HIR/MIR; el compilador autoalojado mantiene su emisor C99 directo
  y su perfil medido en la matriz de paridad.
- Se registraron en [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md) los hallazgos de
  auditoría que siguen abiertos: representación `WVal`, coste de CoW, verificación de
  funciones genéricas no instanciadas, benchmarks y recuperación sintáctica.
- La ABI C existente se conserva en esta versión; sus tipos y nombres documentados
  siguen siendo parte del contrato actual.

### Verificación

La versión solo debe etiquetarse cuando pasen las puertas `release`, la suite de
conformidad, el bootstrap determinista, los tests Python y las validaciones de
sanitizers/distribución en los sistemas soportados. Esta rama no afirma que una
publicación oficial ya se haya realizado.
