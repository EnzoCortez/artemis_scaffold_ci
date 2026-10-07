# 4.2. Limitaciones y Restricciones del Proyecto

Para evitar ambigüedades en el desarrollo, alcance y evaluación del producto, se definen las siguientes exclusiones explícitas y condicionantes técnicas. Se categorizan en **Limitaciones** (funcionalidades y características que no se incluirán en el proyecto) y **Restricciones** (reglas técnicas, operativas y de entorno que deben cumplirse obligatoriamente).

---

### Limitaciones (Fuera del Alcance)
*   **Actuación directa (Push):** Artemis no realizará conexiones directas a los dispositivos de seguridad (ej. mediante SSH o Telnet) para configurar reglas; el sistema solo expone las listas para que los equipos perimetrales realicen el consumo de forma asíncrona (Pull).
*   **Correlación de eventos:** El sistema no actuará como un SIEM (Security Information and Event Management); no ingesta ni analiza tráfico de red, logs de navegación o alertas de intrusión. Su dominio se limita estrictamente a la gestión del inventario de Indicadores de Compromiso (IoCs).
*   **Enriquecimiento externo:** No se contempla el desarrollo de integraciones con APIs públicas de reputación de terceros (ej. VirusTotal, AlienVault) en esta primera versión (MVP), recayendo la responsabilidad de la inteligencia inicial en el analista.
*   **Aplicación Móvil:** No se desarrollará una app móvil nativa (Android/iOS) para la plataforma. La administración se realizará a través de la aplicación web, la cual estará optimizada principalmente para resoluciones de escritorio, dada la naturaleza operativa del analista SOC.
*   **Ciberinteligencia Activa:** El sistema no cuenta con *crawlers* o *scrapers* para buscar amenazas proactivamente en la web pública o Dark Web; funcionará puramente como un orquestador pasivo que valida y enruta los datos que se le ingresan explícitamente.

---

### Restricciones (Condicionantes de Diseño y Desarrollo)
*   **Entorno de Despliegue (On-Premise):** Por normativas de confidencialidad de la entidad bancaria, el sistema debe alojarse y ejecutarse íntegramente en servidores locales. Se prohíbe el uso de infraestructuras en la Nube Pública (AWS, Azure, GCP) o clústeres nativos de Linux (Docker, Kubernetes).
*   **Pila Tecnológica:** El sistema web backend deberá desarrollarse en lenguaje Python (Framework Django) y deberá ejecutarse obligatoriamente sobre el sistema operativo Windows Server (2019/2022) utilizando Internet Information Services (IIS) como servidor web (Proxy Inverso).
*   **Motor de Base de Datos:** La persistencia de la información y la auditoría deben realizarse exclusivamente utilizando Microsoft SQL Server, utilizando transacciones seguras mediante el protocolo TDS.
*   **Tiempos de Respuesta (Rendimiento):** El motor de validación e ingesta masiva deberá ser capaz de procesar, validar matemáticamente y almacenar un lote estándar de 5,000 indicadores en un tiempo máximo de 5 segundos.
*   **Estándares Web:** La interfaz de usuario no tendrá soporte para navegadores heredados (como Internet Explorer). El sistema web funcionará únicamente en navegadores modernos con compatibilidad total para HTML5 y JavaScript ES6+.
*   **Controles de Seguridad:** El acceso a la plataforma web debe realizarse estrictamente a través de protocolos cifrados (HTTPS/TLS 1.2+). Asimismo, la persistencia de contraseñas debe regirse por algoritmos de hashing fuertes (PBKDF2-SHA256).
