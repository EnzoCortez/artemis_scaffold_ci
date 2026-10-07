/* 
   Script de Migración Manual de Esquema para Artemis
   --------------------------------------------------
   Este script mueve las tablas de 'ioc_manager' desde el esquema standard 'dbo' 
   al esquema dedicado 'artemis_db' y las renombra para coincidir con la configuración de Django.

   INSTRUCCIONES:
   1. Ejecutar en SQL Server Management Studio (SSMS).
   2. Asegurarse de estar conectado a la base de datos correcta.
*/

-- 1. Crear el esquema 'artemis_db' si no existe
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'artemis_db')
BEGIN
    EXEC('CREATE SCHEMA [artemis_db]');
    PRINT '✅ Esquema [artemis_db] creado.';
END
ELSE
BEGIN
    PRINT 'ℹ️ Esquema [artemis_db] ya existe.';
END
GO

-- Helper para mover y renombrar tabla
-- Parametros: @OldName (en dbo), @NewName (en artemis_db)

DECLARE @OldTable NVARCHAR(255);
DECLARE @NewTable NVARCHAR(255);

-- ---------------------------------------------------------
-- TABLA: IocEntry
-- dbo.ioc_manager_iocentry -> artemis_db.ioc_entry
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_iocentry', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_iocentry];
    EXEC sp_rename 'artemis_db.ioc_manager_iocentry', 'ioc_entry';
    PRINT '✅ [ioc_manager_iocentry] movida y renombrada a [artemis_db].[ioc_entry]';
END

-- ---------------------------------------------------------
-- TABLA: Tool
-- dbo.ioc_manager_tool -> artemis_db.tool
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_tool', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_tool];
    EXEC sp_rename 'artemis_db.ioc_manager_tool', 'tool';
    PRINT '✅ [ioc_manager_tool] movida y renombrada a [artemis_db].[tool]';
END

-- ---------------------------------------------------------
-- TABLA: IocType
-- dbo.ioc_manager_ioctype -> artemis_db.ioc_type
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_ioctype', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_ioctype];
    EXEC sp_rename 'artemis_db.ioc_manager_ioctype', 'ioc_type';
    PRINT '✅ [ioc_manager_ioctype] movida y renombrada a [artemis_db].[ioc_type]';
END

-- ---------------------------------------------------------
-- TABLA: IocLoadBatch
-- dbo.ioc_manager_iocloadbatch -> artemis_db.ioc_load_batch
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_iocloadbatch', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_iocloadbatch];
    EXEC sp_rename 'artemis_db.ioc_manager_iocloadbatch', 'ioc_load_batch';
    PRINT '✅ [ioc_manager_iocloadbatch] movida y renombrada a [artemis_db].[ioc_load_batch]';
END

-- ---------------------------------------------------------
-- TABLA: IocLoadResult
-- dbo.ioc_manager_iocloadresult -> artemis_db.ioc_load_result
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_iocloadresult', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_iocloadresult];
    EXEC sp_rename 'artemis_db.ioc_manager_iocloadresult', 'ioc_load_result';
    PRINT '✅ [ioc_manager_iocloadresult] movida y renombrada a [artemis_db].[ioc_load_result]';
END

-- ---------------------------------------------------------
-- TABLA: IocTool (Through Model)
-- dbo.ioc_manager_ioctool -> artemis_db.ioc_tool
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_ioctool', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_ioctool];
    EXEC sp_rename 'artemis_db.ioc_manager_ioctool', 'ioc_tool';
    PRINT '✅ [ioc_manager_ioctool] movida y renombrada a [artemis_db].[ioc_tool]';
END

-- ---------------------------------------------------------
-- TABLA: ToolHashType
-- dbo.ioc_manager_toolhashtype -> artemis_db.tool_hash_type
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_toolhashtype', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_toolhashtype];
    EXEC sp_rename 'artemis_db.ioc_manager_toolhashtype', 'tool_hash_type';
    PRINT '✅ [ioc_manager_toolhashtype] movida y renombrada a [artemis_db].[tool_hash_type]';
END

-- ---------------------------------------------------------
-- TABLA: ToolIndicatorRule
-- dbo.ioc_manager_toolindicatorrule -> artemis_db.tool_indicator_rule
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_toolindicatorrule', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_toolindicatorrule];
    EXEC sp_rename 'artemis_db.ioc_manager_toolindicatorrule', 'tool_indicator_rule';
    PRINT '✅ [ioc_manager_toolindicatorrule] movida y renombrada a [artemis_db].[tool_indicator_rule]';
END

-- ---------------------------------------------------------
-- TABLA: M2M (si existe como tabla automática antigua)
-- dbo.ioc_manager_ioctype_tools -> artemis_db.ioc_manager_ioctype_tools
-- (Normalmente no se renombra si es automática, pero si usas through model IocTool, esta no debería existir o debería borrarse)
-- ---------------------------------------------------------
IF OBJECT_ID('dbo.ioc_manager_ioctype_tools', 'U') IS NOT NULL
BEGIN
    ALTER SCHEMA [artemis_db] TRANSFER [dbo].[ioc_manager_ioctype_tools];
    PRINT '✅ [ioc_manager_ioctype_tools] movida a [artemis_db] (sin renombrar).';
END

PRINT '--- FIN DEL SCRIPT ---';
