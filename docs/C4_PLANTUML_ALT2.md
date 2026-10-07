# Diagrama C4 Nivel 2 en PlantUML (Alternativa 2)

Este es el código fuente en formato **C4-PlantUML** para la arquitectura de microservicios (Alternativa 2) basándome exactamente en tu imagen. También le he aplicado el formato en cuadrícula "S-shape" para que se vea compacto e ideal para documentación.

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

title Diagrama C4 Nivel 2 (Contenedores) - Ecosistema Distribuido (Alternativa 2)

' --- Actores y Sistemas Externos ---
Person(soc_analyst, "Analista SOC", "Gestiona alertas de seguridad y realiza análisis.")

System_Ext(firewall, "Firewall Perimetral", "Red corporativa externa. Filtra tráfico de entrada y salida.")
System_Ext(ips, "Sistema IPS", "Prevención de intrusiones corporativas en tiempo real.")
System_Ext(edr, "Plataforma EDR", "Protección y monitoreo de endpoints corporativos.")

' --- Límite del Sistema (Microservicios) ---
System_Boundary(microservices_system, "Ecosistema Distribuido") {
    
    Container(spa, "SPA", "React / Angular / Vue", "Interfaz web dinámica y reactiva en el navegador.")
    
    Container(api_gateway, "API Router / Gateway", "NGINX", "Punto de entrada único. Enruta peticiones a los microservicios.")
    
    Container(ingestion, "Servicio de Ingesta", "FastAPI - Python", "Carga, limpieza y validación de archivos de logs grandes.")
    
    ContainerDb(database, "Database", "Cluster Mongo DB", "NoSQL persistente y escalable.")
}

' --- Relaciones Optimizadas para evitar cruces ---
Rel_R(soc_analyst, spa, "Interactúa UI", "HTTPS")
Rel_R(spa, api_gateway, "API REST", "HTTPS / JSON")
Rel_D(api_gateway, ingestion, "Delega archivos", "HTTP")

Rel_D(ingestion, database, "Persiste logs", "Driver Mongo")

Rel_R(ingestion, firewall, "Publica feeds IoC", "HTTPS")
Rel_R(ingestion, ips, "Publica feeds IoC", "HTTPS")
Rel_R(ingestion, edr, "Publica feeds IoC", "HTTPS")

@enduml
```
