# ADR-014 · Efectos de expresión, escapes C99 e inicialización de constructores

- **Estado:** Aceptada
- **Fecha:** 2026-10-16
- **Decisores:** Proyecto W

## Contexto

La auditoría de `main` encontró tres fallos de seguridad semántica: los `?` de un
literal podían convertirse en trigraphs durante el preprocesado C99 y cambiar su
longitud; HIR movía fuera de contexto los efectos de asignaciones usadas como
expresiones; y el análisis de constructores contaba asignaciones dentro de ramas que
`and` u `or` podían omitir. Las correcciones deben conservar el mismo contrato en W0,
el backend C99 y W1.

## Decisiones

1. Los generadores C99 escapan cada `?` del texto de usuario como `\077`. La secuencia
   octal de ancho fijo evita que el preprocesador reconozca cualquiera de los nueve
   trigraphs antes de interpretar el literal. W0 AST, W0 HIR y W1 aplican la misma regla.
2. HIR representa una asignación que produce valor con `HirSequence(statements, value)`.
   El backend emite sus efectos cuando visita esa expresión. Así las asignaciones en
   operandos de `and`, `or` y `??` quedan dentro de la rama condicional que los evalúa.
   El verificador limita los efectos de la secuencia a asignaciones y temporales, y el
   verificador de bindings mantiene esos temporales en el ámbito de la expresión.
3. El flujo de inicialización del constructor une los estados de las rutas posibles.
   Las ramas omitibles de `and`, `or` y `??` no inicializan campos de forma definitiva;
   un literal que hace inevitable una rama permite descartar la ruta imposible. W1
   aplica la misma unión al validar sus expresiones tokenizadas.

## Consecuencias

- Los nueve trigraphs de C99 conservan sus bytes originales y no pueden acortar el
  buffer que recibe el runtime.
- Las asignaciones conservan orden, valor y evaluación condicional en Typed HIR,
  incluidas expresiones de nivel superior y expresiones de retorno.
- Un constructor no compila si un campo solo se asigna en una rama que puede omitirse.
  Las ramas de `if`, `and`, `or` y `??` que necesariamente se ejecutan siguen siendo válidas.
- La cobertura de regresión incluye los cuatro motores; las pruebas nativas críticas
  se ejecutan con ASan y UBSan.
