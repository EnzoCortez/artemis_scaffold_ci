USE master;
GO

-- 1. Permiso para ver el tamaño del log (DBCC SQLPERF)
-- Reemplaza 'artemis_user' con el nombre de usuario configurado en tu .env si es diferente.
GRANT VIEW SERVER STATE TO [artemis_user];
GO

USE artemis_db;
GO

-- 2. Permiso para reducir el log (ALTER DATABASE / DBCC SHRINKFILE)
-- Agregar al rol db_owner asegura permisos suficientes para mantenimiento.
ALTER ROLE [db_owner] ADD MEMBER [artemis_user];
GO
