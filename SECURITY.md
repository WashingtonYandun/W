# Política de seguridad

El equipo de Wysna toma en serio la seguridad, la seguridad de memoria y la corrección del compilador. Esta política explica cómo reportar vulnerabilidades, cómo respondemos y qué versiones reciben soporte.

## Versiones con soporte

Solo la línea menor más reciente recibe actualizaciones de seguridad y backports.

| Versión | Soporte | Estado de seguridad |
| --- | --- | --- |
| 0.5.0 | ⏳ | Candidata no publicada; el soporte oficial comienza tras superar CI multiplataforma |
| 0.4.0a1 | ❌ | Reemplazada por la candidata Wysna 0.5.0 |
| 0.3.0.dev1 | ❌ | Reemplazada por la línea alpha Wysna 0.4.0 |
| 0.2.x | ❌ | Reemplazada por Wysna 0.3.0 |
| 0.1.x | ❌ | Versión histórica sin soporte |
| < 0.1.0 | ❌ | Versiones experimentales sin soporte |

## Reportar una vulnerabilidad

Si encuentras una vulnerabilidad en el compilador, runtime o herramientas de Wysna, **no la reportes mediante un issue público de GitHub**. Usa uno de estos canales de divulgación responsable:

1. **GitHub Security Advisory (preferido):** crea un reporte privado en [github.com/WashingtonYandun/Wysna/security/advisories/new](https://github.com/WashingtonYandun/Wysna/security/advisories/new).
2. **Correo electrónico:** escribe a [washington.yandun.morales@gmail.com](mailto:washington.yandun.morales@gmail.com), con el asunto `[SECURITY]`.

### Información necesaria

- Descripción de la vulnerabilidad y, si está disponible, evaluación de severidad (CVSS).
- Ejemplo mínimo en Wysna (`.wysna`) o script que reproduzca el problema.
- Componente afectado, por ejemplo runtime C99 (`runtime/wysna_runtime.h`), lowerer HIR, generador C, parser o compilador autoalojado.
- Entorno exacto: sistema operativo, arquitectura, versión de Wysna (`./wysna version`) y toolchain C (`clang --version` o `gcc --version`).
- Traza del sanitizer cuando corresponda (ASan/UBSan con `./wysna run <file>.wysna`).

## Proceso de respuesta

1. **Acuse de recibo:** confirmaremos la recepción dentro de **48 horas**.
2. **Evaluación y triage:** investigaremos y evaluaremos la vulnerabilidad dentro de **5 días laborables**, validando reproducción e impacto.
3. **Corrección:** desarrollaremos el arreglo en una rama privada y lo verificaremos con AddressSanitizer, UndefinedBehaviorSanitizer y pruebas diferenciales.
4. **Release y advisory:** publicaremos una versión correctiva y un GitHub Security Advisory coordinado. Daremos crédito a quien reportó el problema, salvo que solicite anonimato.

## Áreas dentro del alcance

- **Seguridad de memoria del runtime C99:** use-after-free, double-free, referencias colgantes, desbordamientos o underflow/overflow del contador de referencias en `runtime/wysna_runtime.h`.
- **Confusión de tipos:** bypasses del verificador estático (`checker/TypeChecker.py`) o HIR tipada que permitan acceso a memoria no verificado.
- **Inyección de código del compilador:** literales o identificadores sin sanitizar que escapen del lowering AST y produzcan ejecución C arbitraria.
- **Invariantes de Copy-on-Write:** mutaciones visibles en valores compartidos entre ámbitos que violen la semántica de valor de Wysna.

## Fuera del alcance

- Denegación de servicio por archivos excesivamente grandes o expresiones muy anidadas que alcancen los límites de recursión del parser, salvo que evadan las protecciones de profundidad del AST.
- Vulnerabilidades que requieran acceso root/administrador o manipulación de binarios locales fuera de la toolchain Wysna.
