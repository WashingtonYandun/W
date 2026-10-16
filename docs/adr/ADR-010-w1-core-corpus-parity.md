# ADR-010: Objetivo de paridad de W1 en el corpus principal

Estado: Aceptada e implementada (F01 cerrada)
Fecha: 2026-10-15

## Contexto

W1 es el compilador autoalojado y la implementación usada para el bootstrap. Al abrir F01,
98 de los 114 fixtures públicos pasaban en W1; 15 fixtures genéricos y uno de módulos
comprobados estaban declarados como no soportados. El proyecto también tiene una suite de
expansión de Fase E, cuya cobertura por backend es distinta a la del corpus principal.

## Decisión

El cierre de las 16 exclusiones de W1 se siguió como hito F01. El 2026-10-15, los 114
fixtures pasaron en los cuatro motores y el perfil `release` terminó sin fallos ni
exclusiones. El bootstrap de tres etapas produjo hashes SHA256 idénticos para las tres
versiones del C emitido.

F01 exige comportamiento observable, no duplicar la arquitectura interna: W1 puede
conservar su frontend de expansión de módulos si compila el fixture de módulos comprobados
y preserva correctamente la identidad de declaraciones importadas y su especialización
genérica. La paridad de la expansión de Fase E se especifica aparte en sus contratos de
prueba.

## Consecuencias

- `tests/engine_profiles.json` ya no declara exclusiones; las 15 fixtures genéricas y el
  fixture de módulos comprobados pasan directamente con W1.
- La especialización genérica, los diagnósticos de ciclo y la especialización importada
  tienen regresiones directas en `tests/unit/test_w1_generic_functions.py` y el corpus.
- El punto fijo del bootstrap se verifica aparte: es necesario, pero por sí solo no
  satisface F01.
- F01 no promete soporte completo para todo programa W posible ni para cada prueba de Fase
  E en W1.
- Las capturas mutables, las uniones de errores y la concurrencia siguen siendo decisiones
  de diseño separadas.
