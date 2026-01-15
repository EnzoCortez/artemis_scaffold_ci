import time
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Shrinks the SQL Server transaction log file to free up space.'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando proceso de optimización de logs...")
        
        with connection.cursor() as cursor:
            # 1. Detectar nombre de la BD actual
            cursor.execute("SELECT DB_NAME()")
            db_name = cursor.fetchone()[0]
            self.stdout.write(f"Base de datos conectada: {db_name}")

            # 2. Detectar nombre lógico del archivo de Log
            # Buscando en sys.database_files (vista local de la BD actual)
            cursor.execute("SELECT name FROM sys.database_files WHERE type_desc = 'LOG'")
            row = cursor.fetchone()
            if not row:
                 self.stdout.write(self.style.ERROR("Error: No se encontró el archivo de log en sys.database_files."))
                 return
            
            log_name = row[0]
            self.stdout.write(f"Archivo de log identificado: {log_name}")

            # 3. Cambiar a Recovery Model SIMPLE
            # Esto trunca el log automáticamente al hacer checkpoints (y permite shrinking inmediato)
            self.stdout.write(f"Cambiando '{db_name}' a modo SIMPLE recovery...")
            try:
                cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY SIMPLE")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"No se pudo cambiar modo de recuperación (posiblemente falta de permisos o conexiones abiertas): {e}"))
                self.stdout.write("Intentando SHRINK directamente...")

            # 4. Shrink File
            target_size_mb = 10
            self.stdout.write(f"Reduciendo '{log_name}' a {target_size_mb} MB...")
            try:
                cursor.execute(f"DBCC SHRINKFILE ('{log_name}', {target_size_mb})")
                self.stdout.write(self.style.SUCCESS("comando DBCC SHRINKFILE ejecutado correctamente."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Falló el shrink: {e}"))
                return

            # Opcional: Volver a FULL si fuera produccion real, pero para Dev/Testing mejor dejar en simple.
            # cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY FULL")

            self.stdout.write(self.style.SUCCESS(f"¡Listo! El espacio en disco de '{db_name}' ha sido recuperado."))
