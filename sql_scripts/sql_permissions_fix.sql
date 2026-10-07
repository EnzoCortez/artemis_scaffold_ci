USE Artemis_db;
GO

-- =============================================
-- Script de Permisos para Usuario 'Artemis'
-- Requerido para Dashboard de Mantenimiento (Log Size & Shrink)
-- Ejecutar como SA o Administrador de Base de Datos
-- =============================================

-- 1. Permiso para ver estadísticas de uso del Log (sys.dm_db_log_space_usage)
-- NECESARIO aunque el usuario sea db_owner en ciertos entornos restrictivos.
GRANT VIEW DATABASE STATE TO [Artemis];
GO

-- 2. Permiso para cambiar el modo de recuperación y reducir archivos (ALTER DATABASE, DBCC SHRINKFILE)
-- db_owner debería tenerlo, pero se recomienda explícito si falla.
GRANT ALTER ON DATABASE::[Artemis_db] TO [Artemis];
GO

-- 3. Verificación de permisos asignados
SELECT pr.name, pe.permission_name, pe.state_desc
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pe.grantee_principal_id = pr.principal_id
WHERE pr.name = 'Artemis';
GO
