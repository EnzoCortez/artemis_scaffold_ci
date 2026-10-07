# Metodologías Ágiles en Artemis: Scrum y Extreme Programming (XP)

El proyecto Artemis se desarrollará bajo un enfoque ágil híbrido, combinando el marco de gestión de **Scrum** con las prácticas rigurosas de ingeniería de software de **Extreme Programming (XP)**. 

Esta combinación (a menudo llamada *Scrum/XP Hybrid*) garantiza tanto la alineación constante con los objetivos operativos del banco como una altísima calidad y seguridad en el código fuente.

---

## 1. Aplicación de Scrum (Marco de Gestión Operativa)

Scrum proporciona la estructura iterativa y los roles necesarios para mantener el proyecto organizado frente a la incertidumbre.

*   **Roles:**
    *   **Product Owner (PO):** Actuará como el representante directo de las necesidades del banco y de los Analistas SOC. Se encargará de priorizar el *Product Backlog* (por ejemplo, decidiendo que el módulo de validación criptográfica de IoCs tiene mayor prioridad que la exportación en CSV).
    *   **Scrum Master:** Facilitará que el equipo elimine bloqueos o impedimentos técnicos (por ejemplo, gestionando bloqueos de puertos en el Firewall, o resolviendo permisos de ejecución de Python dentro de Windows IIS).
    *   **Development Team:** Responsables de la construcción técnica de la aplicación web, el desarrollo en Django, la Base de Datos y la UI.

*   **Eventos (Ceremonias):**
    *   **Sprints:** El proyecto operará en iteraciones de **2 semanas** (ya documentadas en el Plan de Releases de 6 Sprints).
    *   **Sprint Planning:** Al inicio de cada quincena se tomarán las Historias de Usuario (HU) más prioritarias y se descompondrán en tareas técnicas.
    *   **Daily Scrum:** Sincronización diaria rápida para detectar cuellos de botella tempranos en el desarrollo.
    *   **Sprint Review & Retrospective:** Al finalizar el Sprint, se despliega una versión del sistema en ambiente de prueba (Staging) demostrando *software funcionando*, y se revisan mejoras metodológicas.

*   **Artefactos:**
    *   **Product Backlog:** Ya documentado en la Planificación con las 9 Historias de Usuario (HUs).
    *   **Sprint Backlog:** Sub-tareas técnicas.
    *   **Incremento del Producto:** Cada 2 semanas, el código integrado e instalable en el servidor.

---

## 2. Aplicación de Extreme Programming - XP (Prácticas de Ingeniería)

Mientras Scrum dice *cómo gestionar el trabajo*, XP dicta *cómo escribir el código de manera segura y eficiente*. La adopción de las siguientes prácticas de XP es crítica para Artemis debido a la naturaleza de ciberseguridad del proyecto:

*   **Desarrollo Guiado por Pruebas (TDD - Test Driven Development):** 
    Es fundamental para la ingesta de IoCs. Antes de programar las funciones finales, se deben escribir las pruebas unitarias (como ya se ha diseñado en `tests/test_regex.py`). Esto asegura desde el minuto uno que ningún formato de IP, URL o Hash inválido o malicioso pueda evadir las defensas del sistema y ensuciar la base de datos de producción.
*   **Integración Continua (CI - Continuous Integration):** 
    Alineado con nuestro plan CI/CD. Los desarrolladores integrarán y subirán código (Push) múltiples veces al día. El servidor de CI validará instantáneamente mediante *linting*, análisis de seguridad estático (SAST) y ejecución automática de las pruebas TDD, rechazando código que rompa las funcionalidades previas.
*   **Diseño Simple (Simple Design):** 
    Uno de los pilares de XP es hacer "la cosa más simple que pueda funcionar". La elección arquitectónica de Artemis (Alternativa 1: Arquitectura Monolítica Modular) es el máximo reflejo de esta práctica. En lugar de complicar el despliegue con orquestadores, Docker o Microservicios complejos, se optó por un monolito optimizado en Django que corre nativamente tras IIS, satisfaciendo todas las restricciones operativas sin añadir sobrecarga técnica.
*   **Refactorización Continua (Refactoring):** 
    El código de Artemis (los modelos en `models.py` o las vistas del Dashboard) se someterá a limpieza continua para eliminar redundancias (principio DRY). Por ejemplo, el motor central de deduplicación se aislará en funciones utilitarias que puedan ser invocadas por cualquier módulo sin reescribir lógica.
*   **Estándares de Codificación (Coding Standards):** 
    El código en Python se someterá a validaciones automáticas contra el estándar **PEP-8**. Esto garantiza que el código sea predecible, uniforme y fácil de mantener, independientemente de qué miembro del equipo asuma el desarrollo a futuro.

## Conclusión
Implementar Scrum garantiza el cumplimiento de la visión del negocio (las reglas del banco y las fechas de la rúbrica), mientras que Extreme Programming blinda la integridad de la plataforma. La simbiosis resultante es un software que se entrega iterativamente, rápido y con la rigurosidad técnica que demanda el área de ciberseguridad.
