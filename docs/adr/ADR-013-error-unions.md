# ADR-013 · Uniones cerradas en el canal de error

- **Estado:** Aceptada
- **Etapa:** F03
- **Fecha:** 2026-10-15
- **Decisores:** Proyecto W

## Contexto

El operador `?` solo propagaba errores cuando el tipo del resultado de origen coincidía
exactamente con el canal de error de la función actual. Eso impedía componer funciones
que fallan con tipos distintos y obligaba a traducir manualmente cada error en cada sitio
de llamada. Una conversión implícita habría ocultado el cambio de payload y debilitado la
exhaustividad.

## Decisión

1. `T ! E1 | E2` declara un conjunto cerrado de alternativas exclusivamente en el canal
   de error. No se introduce sintaxis de unión general.
2. El conjunto requiere al menos dos alternativas distintas. La interning elimina
   duplicados y produce identidad canónica independiente del orden escrito.
3. Se admiten `int`, `float`, `bool`, `str`, `struct` no genéricos y `enum` no genéricos.
   Se excluyen clases, genéricos, colecciones, tuplas, funciones y otros tipos compuestos:
   WVal aún no conserva para ellos una identidad runtime concreta y no ambigua.
4. `?` propaga si cada alternativa de origen está incluida en el conjunto de destino.
   El conjunto destino no puede perder alternativas y el payload no se convierte ni se
   envuelve nuevamente.
5. Un `Result[T, E1]` completo puede asignarse o retornarse como `Result[T, E2]` solo si
   `T` es idéntico y cada alternativa de `E1` aparece en `E2`. El valor etiquetado se
   conserva tal cual: no se convierte en `Ok` ni se aplanan capas `Result` anidadas.
6. `else err` liga el payload original con el tipo estático de la unión. Un `match` que
   produce un valor debe cubrir cada tipo mediante `Tipo(binding)` o `Tipo(_)`; los
   tipos exportados aceptan su calificador de módulo, como `storage.ParseError(error)`.
   El binding representa el valor de error completo.
7. Los backends comparan la identidad runtime del valor: tags escalares para primitivos,
   nombre nominal para `struct` y nombre nominal para `enum`. No se añade wrapper ni ABI
   nuevo a Result.
8. W1 implementa la misma sintaxis, reglas de propagación, validación de alternativas,
   binding de error y cobertura exhaustiva. La matriz release mide su paridad frente a W0.

## Consecuencias

- `ParseError` se puede propagar a `ParseError | IoError`; `ParseError | IoError` no se
  puede propagar a una función que solo declara `ParseError`.
- Un `Result[T, ParseError]` se puede devolver como `Result[T, ParseError | IoError]`;
  `Result[T, ParseError]` no se puede devolver como `Result[T, IoError]` ni como
  `Result[T, Result[ParseError, OtherError]]`.
- La comprobación exhaustiva detecta alternativas omitidas en `match err`.
- Se conserva el payload y su ownership ARC/CoW actual en intérprete, AST C99, HIR C99
  y W1.
- Ampliar este conjunto requiere definir primero una identidad runtime segura para cada
  categoría excluida.

## Evidencia requerida

`tests/runtime/error_union_composition.w` debe ejecutar cada alternativa y comparar
salida entre los cuatro motores. Las pruebas negativas rechazan propagación fuera del
conjunto, `match` no exhaustivo, alternativas sin identidad runtime admitida y
subpatrones de payload que los backends no pueden comprobar. La suite release y el
bootstrap de tres etapas deben pasar sin exclusiones ni divergencias.
