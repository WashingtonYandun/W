# ADR-010: Objetivo de paridad de W1 en el corpus principal

Estado: Aceptada
Fecha: 2026-10-15

## Contexto

W1 es el compilador autoalojado y la implementación usada para el bootstrap. Actualmente
pasa 98 de los 114 fixtures públicos del corpus principal. Quince fixtures de genéricos y
uno de módulos comprobados están declarados como no soportados. Algunos documentos
asignaban este trabajo a D02, aunque D02 ya figura como el checker semántico guiado por
tokens. El proyecto también tiene una suite de expansión de Fase E, cuya cobertura por
backend es distinta a la del corpus principal.

## Decisión

El cierre de las 16 exclusiones actuales de W1 se seguirá como hito F01. F01 termina cuando
los 114 fixtures pasan en los cuatro motores y el perfil de conformidad `release` funciona
sin exclusiones de capacidades.

F01 exige comportamiento observable, no duplicar la arquitectura interna: W1 puede
conservar su frontend de expansión de módulos si compila el fixture de módulos comprobados
y preserva correctamente la identidad de declaraciones importadas y su especialización
genérica. La paridad de la expansión de Fase E se especifica aparte en sus contratos de
prueba.

## Consecuencias

- El identificador de seguimiento activo en `tests/engine_profiles.json` es F01; D02 queda
  como referencia histórica.
- La especialización genérica y la especialización de imports deben tener pruebas directas
  con W1 antes de retirar las exclusiones.
- Pasar el punto fijo del bootstrap no satisface F01.
- F01 no promete soporte completo para todo programa W posible ni para cada prueba de Fase
  E en W1.
- Las capturas mutables, las uniones de errores y la concurrencia siguen siendo decisiones
  de diseño separadas.
