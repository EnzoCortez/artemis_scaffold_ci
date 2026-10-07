# -*- coding: utf-8 -*-
from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
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
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        qs = IocEntry.objects.all()

        if start_date:
            parsed_start = parse_date(start_date)
            if parsed_start:
                qs = qs.filter(created_at__gte=parsed_start)
        
        if end_date:
            parsed_end = parse_date(end_date)
            if parsed_end:
                # Se suma un día implícitamente o se busca <=
                # Como created_at es datetime, <= a la fecha (medianoche) no incluirá lo del día, pero usaremos date()
                qs = qs.filter(created_at__date__lte=parsed_end)

        # 1. Total IOCs
        total_iocs = qs.count()
        total_bloqueados = qs.filter(status=IocEntry.STATUS_BLOCKED).count()
        total_depurados = qs.filter(status=IocEntry.STATUS_CLEARED).count()
        
        # 2. Por Tipo (Pie Chart)
        by_type = list(qs.values('ioc_type__name').annotate(count=Count('id')).order_by('-count'))
        
        # 3. Por Estado (Bar/Doughnut Chart)
        by_status = list(qs.values('status').annotate(count=Count('id')).order_by('status'))

        # 4. Por Mes cronológicamente (Line/Bar Chart)
        from django.db.models.functions import TruncMonth
        by_month = list(
            qs.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                count=Count('id'),
                blocked_count=Count('id', filter=Q(status=IocEntry.STATUS_BLOCKED))
            )
            .order_by('month')
        )
        
        # Format month explicitly for JSON serialization
        formatted_by_month = [
            {
                "month": m["month"].strftime("%Y-%m") if m["month"] else "Unknown", 
                "count": m["count"],
                "blocked_count": m["blocked_count"]
            }
            for m in by_month
        ]

        return Response({
            "total": total_iocs,
            "total_bloqueados": total_bloqueados,
            "total_depurados": total_depurados,
            "by_type": by_type,
            "by_status": by_status,
            "by_month": formatted_by_month
        })


class UploadHistoryView(APIView):
    """Historial de lotes de carga con datos para gráfico de barras."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import IocLoadBatch

        qs = IocLoadBatch.objects.select_related('uploaded_by').order_by('-created_at')[:50]

        history = []
        for batch in qs:
            history.append({
                "id": batch.id,
                "source": batch.source,
                "total": batch.total,
                "inserted": batch.inserted,
                "duplicated": batch.duplicated,
                "rejected": batch.rejected,
                "uploaded_by": batch.uploaded_by.username if batch.uploaded_by else "Sistema",
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "batch_uuid": batch.batch_uuid or ""
            })

        return Response({"history": history})
