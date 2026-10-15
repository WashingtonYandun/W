# ADR-011 · Clases e interfaces genéricas

Estado: implementación inicial en W0; paridad W1 pendiente.

Se especializan clases e interfaces por identidad nominal de plantilla y tupla de TypeIds de una sesión. Dos usos de `Repository[int]` comparten especialización; `Repository[str]` tiene una identidad distinta. Los argumentos de tipos son invariantes.

Cada especialización genera campos y métodos concretos. Conserva las comprobaciones existentes de interfaces, visibilidad, overrides y constructores. El backend mantiene actualmente su dispatcher de métodos por clase. Esta decisión no afirma que ya existan vtables indexadas: sustituir ese dispatcher requiere otra implementación y pruebas de ABI.

Se limita la profundidad de especialización a 32 y el número de instancias por plantilla a 256 para evitar expansión sin límite. Superar el presupuesto produce W2011. Estos límites son una protección del compilador, no una prueba matemática de terminación.

Elegimos especialización frente a type erasure porque comparte la representación actual de tipos y no introduce boxing nuevo ni casts entre firmas C. El coste es tamaño de código proporcional a las combinaciones usadas. Antes de cambiar a vtables especializadas se deben medir tamaño de binario, número de métodos emitidos y coste del dispatch con programas representativos.
