# -*- coding: utf-8 -*-
from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count
from .models import IocEntry, IocType

class DBLogSizeView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Obtiene el tamaño del log de transacciones."""
        try:
            with connection.cursor() as cursor:
                # DMV: sys.dm_db_log_space_usage (Requires VIEW DATABASE STATE, included in db_owner)
                # Returns: total_log_size_in_bytes, used_log_space_in_percent
                cursor.execute("SELECT (total_log_size_in_bytes / 1048576.0), used_log_space_in_percent FROM sys.dm_db_log_space_usage")
                row = cursor.fetchone()
                
                if row:
                    log_info = {
                        'db_name': settings.DATABASES['default']['NAME'],
                        'size_mb': float(row[0]),
                        'used_percent': float(row[1]),
                        'status': 'ONLINE'
                    }
                    return Response(log_info)
                else:
                    return Response({"error": "No log usage info returned for current DB"}, status=404)

        except Exception as e:
            error_str = str(e)
            print(f"DEBUG: Error in DBLogSizeView: {error_str}")
            if "permission" in error_str.lower() or "42000" in error_str:
                return Response({"error": "Permisos insuficientes en SQL Server. Ejecuta grant_permissions.sql"}, status=403)
            return Response({"error": error_str}, status=500)

class DBLogShrinkView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        """Reduce el tamaño del log de transacciones."""
        db_name = settings.DATABASES['default']['NAME']
        
        try:
            # IMPORTANT: ALTER DATABASE and DBCC commands often require no active transaction.
            connection.set_autocommit(True)
            
            with connection.cursor() as cursor:
                # 1. Obtener nombre lógico del archivo LOG
                # REMOVED: USE [{db_name}]; as connection is already set to DB
                cursor.execute("SELECT name FROM sys.database_files WHERE type_desc = 'LOG'")
                row = cursor.fetchone()
                if not row:
                     print(f"DEBUG: No LOG file found for {db_name}")
                     return Response({"error": "No logic log file found"}, status=500)
                
                log_file_name = row[0]
                print(f"DEBUG: Found Log File '{log_file_name}' for DB '{db_name}'. Starting Shrink...")

                # 2. Ejecutar secuencia de Shrink step-by-step for better error isolation
                try:
                    cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY SIMPLE")
                    print("DEBUG: Set RECOVERY SIMPLE success.")
                    
                    cursor.execute(f"DBCC SHRINKFILE([{log_file_name}], 1)")
                    print("DEBUG: DBCC SHRINKFILE success.")
                    
                    cursor.execute(f"ALTER DATABASE [{db_name}] SET RECOVERY FULL")
                    print("DEBUG: Set RECOVERY FULL success.")
                    
                except Exception as ex_sql:
                    print(f"DEBUG: SQL Execution Error: {ex_sql}")
                    raise ex_sql
                
            return Response({"message": f"Log ({log_file_name}) shrink completed successfully."})

        except Exception as e:
            print(f"DEBUG: General Error in Shrink: {e}")
            return Response({"error": str(e)}, status=500)


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retorna estadísticas para los gráficos."""
        # 1. Total IOCs
        total_iocs = IocEntry.objects.count()
        
        # 2. Por Tipo (Pie Chart)
        by_type = list(IocEntry.objects.values('ioc_type__name').annotate(count=Count('id')).order_by('-count'))
        
        # 3. Por Estado (Bar/Doughnut Chart)
        # MSSQL Fix: Explicitly order by (e.g. status) to avoid default ordering on 'created_at' which breaks GROUP BY
        by_status = list(IocEntry.objects.values('status').annotate(count=Count('id')).order_by('status'))

        return Response({
            "total": total_iocs,
            "by_type": by_type,
            "by_status": by_status
        })
