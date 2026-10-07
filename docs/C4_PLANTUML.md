# Diagrama C4 Nivel 2 en PlantUML

A continuación tienes el código fuente exacto para generar el Diagrama de Contenedores usando el estándar **C4-PlantUML**. Puedes copiar y pegar este bloque en cualquier renderizador que soporte PlantUML (como la extensión de Visual Studio Code o servidores online como PlantText).

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

title Diagrama C4 Nivel 2 (Contenedores) - Arquitectura Monolítica Modular (Artemis)

' --- Actores y Sistemas Externos ---
Person(soc_analyst, "Analista SOC", "Carga IoCs y gestiona el ciclo de vida.")

System_Ext(firewall, "Firewall Perimetral", "Red corporativa externa.")
System_Ext(ips, "Sistema IPS", "Prevención de intrusiones.")
System_Ext(edr, "Plataforma EDR", "Protección de endpoints.")

' --- Límite del Sistema Artemis ---
System_Boundary(artemis_system, "Plataforma de Gestión de Inteligencia (Artemis)") {
    
    Container(web_server, "Servidor Proxy Inverso", "IIS", "Termina TLS/HTTPS y enruta el tráfico interno.")
    
    Container(wsgi_server, "Servidor de Aplicaciones", "Waitress WSGI", "Procesa concurrencia y actúa como puente HTTP a Python.")
    
    Container(frontend_app, "Aplicación Frontend (SPA)", "JavaScript, HTML, CSS", "Provee el Dashboard e interfaz gráfica en el navegador del usuario.")
    
    Container(web_app, "Aplicación Backend Core", "Python, Django REST", "API REST segura, motor de validación, deduplicación y ruteo.")
    
    ContainerDb(database, "Base de Datos", "MS SQL Server", "Persiste IoCs, configuraciones de herramientas y auditoría transaccional ACID.")
}

' --- Relaciones de Consumo (Externas) ---
Rel_R(soc_analyst, frontend_app, "Interactúa con la interfaz", "HTTPS")
Rel_D(frontend_app, web_server, "Realiza peticiones API", "HTTPS / JSON")

Rel_L(firewall, web_server, "Consume feed", "HTTPS")
Rel_L(ips, web_server, "Consume feed", "HTTPS")
Rel_L(edr, web_server, "Consume feed", "HTTPS")

' --- Relaciones Internas ---
Rel_L(web_server, wsgi_server, "Enruta tráfico", "HTTP Loopback")
Rel_D(wsgi_server, web_app, "Ejecuta", "WSGI Call")
Rel_R(web_app, database, "Lee/escribe", "ODBC/TDS")

@enduml
```
