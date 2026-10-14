# ADR-005: hardening de genéricos, límites de instanciación y telemetría

## Estado

Aceptado para v0.2.1; corregido tras la auditoría del merge a4397d3.
Esta revisión sustituye las garantías de detección inmediata por complejidad creciente y de hash estable entre procesos de la versión inicial del ADR.

## Contexto

El cache de especializaciones necesita claves inmutables y métricas verificables. La implementación inicial rechazaba una nueva instancia cuando su complejidad superaba la de una instancia activa de la misma plantilla. Ese aumento no demuestra expansión infinita: una llamada a una especialización explícita mayor puede converger a una instancia ya cacheada.

Ejemplo: fixed[int] llama a fixed[list[int]], y esta última se llama a sí misma con list[int]. El conjunto contiene dos instancias aunque la ejecución de esa función no termine. No debe confundirse recursión runtime con expansión del compilador.

## Decisiones

1. GenericInstanceKey es una tupla nombrada inmutable de nombre de plantilla y tuple de TypeId. Su identidad y cache son locales al TypeChecker. El hash interno depende del proceso Python; no forma parte de la ABI ni del mangling. La identidad por módulo/DeclId queda pendiente del plan arquitectónico.
2. Cache-first: reutilizar una instancia antes de aplicar el límite de profundidad. Esto permite recurrencia de la misma instancia incluso en la frontera del presupuesto.
3. Una cadena puede tener hasta 64 instanciaciones nuevas activas. Intentar otra produce W2011 indicando agotamiento del límite de profundidad. No se presenta como prueba de ciclo infinito. Una cadena finita que exceda el presupuesto también puede rechazarse.
4. Se retira el rechazo basado exclusivamente en aumento de complejidad. El análisis estructural completo, ciclos mutuos generales y budgets globales de instancias/memoria quedan pendientes. El cálculo de complejidad usa los campos reales de los tipos semánticos; no es una prueba de terminación.
5. Se conserva la política actual de rechazo sintáctico de recursión directa en structs genéricos (W2011) y enums (T025). No constituye un análisis general de layout: el runtime sigue usando WVal y payloads indirectos. Box ordinario no se declara primitivo de indirección mediante este ADR.
6. Las métricas de codegen cuentan líneas del string C final mediante splitlines y bytes UTF-8. Generated functions incluye helpers/constructores emitidos; las especializaciones de funciones de usuario se contabilizan separadamente en specialized_functions. No se deduce tamaño de binario a partir de líneas C.
7. run --stats/--metrics conserva ejecución y stdout del programa; métricas en stderr. emit-c/build también escriben métricas en stderr. check --stats conserva una respuesta JSON en stdout. Run reporta monomorfización, no codegen que no ejecutó. La telemetría de checker previa a ejecución no certifica éxito runtime.

## Evidencia y límites

La suite test_generic_hardening.py cubre inmutabilidad, deduplicación local, tuple/result en el visitor, especializaciones finitas explícitas e inferidas, recursión mutua finita, frontera cache/profundidad, expansión no acotada, volumen C de ambos backends y contrato CLI de stats.

No se garantiza terminación en O(1), deduplicación entre unidades, paridad W1 de genéricos ni layouts C especializados. El límite de profundidad es una defensa de recursos; no reemplaza el trabajo C01–C05 del roadmap. El costo de calcular complejidad depende del tamaño de los argumentos y el del hash depende de la longitud de la clave.
