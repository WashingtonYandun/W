# ADR-015 · Patrones resueltos de tipo de error

- **Estado:** Aceptada
- **Fecha:** 2026-10-16
- **Alcance:** Representación interna W0; semántica F03 compartida con W1

## Contexto

Los patrones de alternativas de error utilizaban `EnumPattern.error_type_match` y se
convertían en `HirEnumPattern` con el nombre ficticio `__W_ERROR_TYPE__`. Una variante
enum y una comprobación de identidad del payload seguían así rutas distintas dentro
del mismo nodo. El verificador y cada consumidor debían interpretar un campo opcional
para decidir qué semántica aplicar.

## Decisión

1. La sintaxis `Type(binding)` conserva su forma. Antes del análisis de tipos, el parser
   sigue usando la forma sintáctica `EnumPattern`: sin conocer el tipo del sujeto no
   puede distinguir una alternativa de error de un constructor enum.
2. Cuando el sujeto es una unión de errores, el checker resuelve la alternativa y
   sustituye esa forma por `ErrorTypePattern`. El nodo guarda el nombre escrito, una
   sola ligadura o wildcard y el tipo resuelto. Un patrón con calificador de módulo se
   resuelve por identidad nominal; el texto visible no decide la comparación runtime.
3. HIR usa `HirErrorTypePattern` con el TypeId de la alternativa y su binding. No tiene
   VariantId, índice de variante ni nombre enum ficticio. `HirEnumPattern` queda reservado
   a variantes enum y a los constructores canónicos Option/Result.
4. El verificador exige que el sujeto sea una unión que contenga la alternativa y que
   el binding tenga el mismo TypeId y sea ligadura o wildcard. Rechaza un patrón enum
   que intente representar una alternativa de esa unión antes de emitir C.
5. Intérprete, AST C99, HIR C99, formatter, bindings y análisis de exhaustividad consumen
   el nodo correspondiente. W1 mantiene su representación por posiciones de tokens;
   los fixtures de los cuatro motores fijan el mismo comportamiento observable.

## Consecuencias y evidencia

La sintaxis pública, las alternativas admitidas y el ABI Result no cambian. Los guards
siguen sin aportar cobertura incondicional. El nombre de fuente se conserva para
formato y dump, mientras la ejecución usa la identidad resuelta.

`test_f03_error_unions.py` verifica la separación de nodos, imports calificados,
patrones locales dentro de bibliotecas importadas, exhaustividad y rechazo de HIR
corrupto. La calificación de módulos resuelve esos nombres locales y conserva su
ortografía de fuente. `error_union_ownership.w` ejercita payloads
gestionados, CoW, guards y propagación bajo los sanitizers y `W_MEM_CHECK`.
