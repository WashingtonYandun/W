# ADR-010 · Funciones y entornos de captura

Estado: implementación experimental.

Las firmas `fn(A, B) -> R` son invariantes. Un valor de función tiene un adaptador con firma C uniforme `WVal (WVal environment, int32_t argc, const WVal* argv)`. Cada adaptador llama a su destino con su firma correcta. No se convierten punteros entre firmas incompatibles.

W0 convierte cada lambda en una función libre y un struct de entorno tipado. W1 conserva los tipos durante el análisis semántico y representa los campos capturados en una tupla de runtime. Ambos entornos residen en heap, pertenecen al valor de función y se liberan mediante ARC.

La captura es por valor: las colecciones y structs conservan snapshots CoW; las clases conservan identidad mediante una referencia fuerte. Los bindings capturados son inmutables. La escritura de campos de una clase capturada sigue las reglas de las clases. Ningún entorno contiene direcciones de variables locales de C.

El lenguaje no ofrece captura por referencia a frames ni acceso mutable a los snapshots. Las closures pueden prolongar ciclos de referencias fuertes; el programador debe romperlos con `Weak`. Los métodos y builtins usados como valores necesitan adaptadores explícitos cuando su contrato difiere del de una función libre.
