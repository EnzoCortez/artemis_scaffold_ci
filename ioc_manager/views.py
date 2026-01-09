# views.py - versión corregida y completa
import io
import uuid
import logging


from django.http import HttpResponse, JsonResponse, request
from django.shortcuts import render
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from ioc_manager.services.ingestion_service import bulk_register_ingestion
from .utils import associate_iocs_with_allowed_tools_bulk
from .utils import detect_ioc_type

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from django.shortcuts import render



from datetime import datetime

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated




from .models import (
    IocEntry,
    IocType,
    IocHistory,
    IocTool,
    Tool,
)


logger = logging.getLogger(__name__)

# mapping tolerante de alias -> nombre canonical en ioc_type
IOC_TYPE_ALIASES = {
    'hash': 'Hash', 'md5': 'Hash', 'sha1': 'Hash', 'sha256': 'Hash', 'sha512': 'Hash',
    'ip': 'IP', 'ipv4': 'IP', 'ipv6': 'IP',
    'correo': 'Correo', 'email': 'Correo',
    'dominio': 'Dominio', 'domain': 'Dominio',
    'url': 'URL', 'http': 'URL', 'https': 'URL'
}

from .models import IocEntry, IocType, IocTool, IocHistory  # ajusta si tus modelos tienen otro nombre
from .serializers import IocEntrySerializer


def is_invalid_value(s):
    "Valores que consideramos inválidos / placeholders y que no deben guardarse."
    if s is None:
        return True
    s = str(s).strip()
    if s == '' or s == '—' or s == '-' or len(s) < 2:
        return True
    return False

@method_decorator(login_required(login_url='/login/'), name='dispatch')
class IndexView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        return render(request, 'ioc_manager/index.html')


class ValidateUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
  
    def post(self, request, format=None):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # 1️⃣ Leer archivo de forma tolerante
        try:
            raw = file_obj.read()
            text = raw.decode('utf-8', errors='ignore')
        except Exception:
            file_obj.seek(0)
            text = b''.join(chunk for chunk in file_obj.chunks()).decode('utf-8', errors='ignore')

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        total = 0
        skipped = []
        clean_values = []

        # 2️⃣ Validación y limpieza
        for line in lines:
            total += 1
            if is_invalid_value(line):
                skipped.append({'line': line, 'reason': 'invalid/placeholder'})
            else:
                clean_values.append(line)

        # eliminar duplicados del archivo
        clean_values = list(set(clean_values))

        # 3️⃣ Query única a BD
        existing_qs = (
            IocEntry.objects
            .filter(value__in=clean_values)
            .select_related('ioc_type')
        )

        # hash map por valor
        existing_map = {ioc.value: ioc for ioc in existing_qs}

        # 4️⃣ Cargar herramientas asociadas (si aplica)
        tools_map = {}
        try:
            ioc_ids = [ioc.id for ioc in existing_qs]
            tool_qs = (
                IocTool.objects
                .filter(ioc_id__in=ioc_ids)
                .select_related('tool')
            )
            for it in tool_qs:
                tools_map.setdefault(it.ioc_id, []).append(it.tool.name)
        except Exception:
            pass

        duplicates = []
        new_items = []

        # 5️⃣ Clasificación final
        for value in clean_values:
            if value in existing_map:
                ioc = existing_map[value]
                duplicates.append({
                    'value': ioc.value,
                    'ioc_type': ioc.ioc_type.name if ioc.ioc_type else '',
                    'tools': tools_map.get(ioc.id, [])
                })
            else:
                try:
                    detected = detect_ioc_type(value)
                except Exception:
                    detected = ''

                new_items.append({
                    'value': value,
                    'detected_type': detected
                })

        # 6️⃣ Respuesta optimizada
        return Response({
            'duplicates': duplicates,
            'new': new_items,
            'skipped': skipped,
            'summary': {
                'total_lines_processed': total,
                'unique_valid': len(clean_values),
                'duplicates': len(duplicates),
                'new': len(new_items),
                'skipped': len(skipped)
            }
        }, status=status.HTTP_200_OK)


class LoadNewIocsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    

    def post(self, request, format=None):

        items = request.data.get('items', [])
        fuente = request.data.get('fuente') or request.data.get('source') or 'Desconocida'

        if not isinstance(items, list):
            return Response({'detail': 'items debe ser una lista'}, status=400)

        batch_id = str(uuid.uuid4())
        user = request.user

        # 🔹 Preload tipos IOC
        ioc_type_map = {
            t.name.lower(): t
            for t in IocType.objects.all()
        }

        values = []
        value_set = set()

        errors = []
        inserted = []
        existing = []

        # 🔹 Normalización previa (O(n))
        for item in items:
            value = item.get('value') if isinstance(item, dict) else str(item)
            if not value:
                continue

            value = value.strip()
            if is_invalid_value(value):
                continue

            value_set.add(value)

        # 🔹 Buscar existentes en una sola query
        existing_map = {
            (e.ioc_type_id, e.value): e
            for e in IocEntry.objects.filter(value__in=value_set)
        }

        to_create = []
        

        for item in items:
            value = item.get('value') if isinstance(item, dict) else str(item)
            if not value:
                continue

            value = value.strip()
            if is_invalid_value(value):
                errors.append({'value': value, 'error': 'invalid'})
                continue

            detected = detect_ioc_type(value)
            ioc_type = ioc_type_map.get((item.get('type') or detected or '').lower())

            if not ioc_type:
                errors.append({'value': value, 'error': 'Tipo IOC no detectado'})
                continue

            key = (ioc_type.id, value)

            if key in existing_map:
                existing.append(value)
                continue

            to_create.append(
                IocEntry(
                    ioc_type=ioc_type,
                    value=value,
                    created_by=user,
                    source=fuente,
                    upload_batch=batch_id
                )
            )
            inserted.append(value)

        # 🔹 Inserción masiva
        IocEntry.objects.bulk_create(
            to_create,
            ignore_conflicts=True,
            batch_size=1000
        )

        # 🔥 RECONSULTAR (ya con ID)
        created_iocs = list(
            IocEntry.objects.filter(upload_batch=batch_id)
            .select_related('ioc_type')
        )
        
        # 🔥🔥🔥 AQUÍ VA EL LLAMADO CORRECTO 🔥🔥🔥
        associate_iocs_with_allowed_tools_bulk(
            list(created_iocs),
            user=request.user
        )


        associate_iocs_with_allowed_tools_bulk(
        list(created_iocs),
        user=request.user
)

        

        return Response({
            'inserted_count': len(created_iocs),
            'existing_count': len(existing),
            'errors': errors,
            'batch_id': batch_id,
            'source': fuente
        }, status=200)




from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import F

from .models import IocEntry


class IocBulkSearchView(APIView):
    """
    POST /api/iocs/bulk-search/
    Body:
    {
        "items": ["ioc1", "ioc2", ...]
    }

    Response:
    {
        "results": [
            { "value": "...", "status": "...", "ioc_type": "..." }
        ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get("items", [])

        if not isinstance(items, list) or not items:
            return Response(
                {"detail": "items debe ser una lista no vacía"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 Normalizar y deduplicar (CRÍTICO)
        values = list({
            str(v).strip()
            for v in items
            if v and str(v).strip()
        })

        if not values:
            return Response({"results": []}, status=status.HTTP_200_OK)

        # 🔥 QUERY ÚNICA, EXACT MATCH
        qs = (
            IocEntry.objects
            .filter(value__in=values)
            .select_related("ioc_type")
            .only("value", "status", "ioc_type__name")
        )

        # 🔹 Respuesta liviana (NO SERIALIZER)
        results = [
            {
                "value": ioc.value,
                "status": ioc.status,
                "ioc_type": ioc.ioc_type.name if ioc.ioc_type else ""
            }
            for ioc in qs
        ]

        return Response({"results": results}, status=status.HTTP_200_OK)



class IocListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    MAX_RESULTS = 50

    def get(self, request):
        q = request.query_params.get("search", "").strip()

        qs = (
            IocEntry.objects
            .select_related("ioc_type")
            .only(
                "id",
                "value",
                "status",
                "created_at",
                "ioc_type__name"
            )
            .order_by("-created_at")
        )

        if q:
            qs = qs.filter(
                Q(value__icontains=q) |
                Q(ioc_type__name__icontains=q)
            )

        qs = qs[:self.MAX_RESULTS]

        serializer = IocEntrySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class ExportIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _build_txt_response(self, queryset, filename):
        def line_iterator():
            for value in queryset.iterator(chunk_size=1000):
                yield f"{smart_str(value)}\n"

        response = HttpResponse(
            line_iterator(),
            content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def get(self, request):
        batch = request.GET.get("batch")

        qs = (
            IocEntry.objects
            .only("value")
            .order_by("value")
        )

        if batch:
            qs = qs.filter(upload_batch=batch)
        else:
            qs = qs.filter(status=IocEntry.STATUS_BLOCKED)

        values = qs.values_list("value", flat=True)
        return self._build_txt_response(values, "iocs_ingestados.txt")

    def post(self, request):
        items = request.data.get("items", [])

        if not isinstance(items, list):
            return Response(
                {"detail": "items debe ser una lista"},
                status=status.HTTP_400_BAD_REQUEST
            )

        cleaned = {
            str(v).strip()
            for v in items
            if v and str(v).strip() not in {"", "-", "--", "—"}
        }

        if not cleaned:
            return Response(
                {"detail": "No hay IoCs válidos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = (
            IocEntry.objects
            .filter(value__in=cleaned)
            .only("value")
            .order_by("value")
            .values_list("value", flat=True)
        )

        return self._build_txt_response(qs, "iocs_ingestados.txt")







class ExportNotIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        if not isinstance(items, list):
            return Response(
                {'detail': 'items debe ser una lista'},
                status=status.HTTP_400_BAD_REQUEST
            )

        items_clean = {str(i).strip() for i in items if str(i).strip()}
        if not items_clean:
            return HttpResponse(
                "",
                content_type='application/zip',
                headers={'Content-Disposition': 'attachment; filename="iocs_no_ingestados.zip"'}
            )

        # IOC existentes
        existing = {
            i.value: i
            for i in IocEntry.objects
                .filter(value__in=items_clean)
                .select_related('ioc_type')
                .prefetch_related('tools')
        }

        classified = {}

        for val in items_clean:
            ioc = existing.get(val)

            # NO existe o existe pero no tiene herramientas
            if not ioc or not ioc.tools.exists():
                ioc_type = (
                    ioc.ioc_type.name.upper()
                    if ioc and ioc.ioc_type
                    else detect_ioc_type(val) or 'DESCONOCIDO'
                )
                classified.setdefault(ioc_type, []).append(val)

        # Generar ZIP
        import zipfile
        from io import BytesIO

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for ioc_type, values in classified.items():
                zf.writestr(
                    f"{ioc_type}.txt",
                    "\n".join(values) + "\n"
                )

        buffer.seek(0)
        return HttpResponse(
            buffer.getvalue(),
            content_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename="iocs_no_ingestados.zip"'}
        )
        
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ioc_manager.services.ingestion_service import validate_and_ingest

class ValidateAndIngestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        fuente = request.data.get('fuente')

        if not items or not fuente:
            return Response({'detail': 'Datos incompletos'}, status=400)

        batch = validate_and_ingest(items, fuente)

        return Response({
            'batch_id': batch.id,
            'inserted': batch.inserted,
            'duplicated': batch.duplicated
        })



# Re-use DRF serializer class for audit as in your code if available:
from rest_framework import serializers as drf_serializers


class AuditCreateSerializer(drf_serializers.Serializer):
    label = drf_serializers.CharField(max_length=200)


class AuditCreateView(APIView):
    #permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AuditCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        label = serializer.validated_data['label']
        h = IocHistory.objects.create(ioc=None, action=f'AUDIT_APPROVED {label}', user=request.user.username, comment=f'Auditoría creada desde UI por {request.user.username}')
        return Response({'audit_id': h.id, 'detail': 'Auditoría registrada'}, status=status.HTTP_201_CREATED)


class PurgeApiSerializer(drf_serializers.Serializer):
    audit_id = drf_serializers.IntegerField()
    dry_run = drf_serializers.BooleanField(default=False)


class PurgeApiView(APIView):
    #permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = PurgeApiSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        audit_id = serializer.validated_data['audit_id']
        dry_run = serializer.validated_data['dry_run']
        try:
            audit = IocHistory.objects.get(id=audit_id)
        except IocHistory.DoesNotExist:
            return Response({'detail': 'Auditoría no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        if 'AUDIT' not in (audit.action or '').upper():
            return Response({'detail': 'Registro de historial proporcionado no es una auditoría válida'}, status=status.HTTP_400_BAD_REQUEST)
        qs = IocEntry.objects.filter(status__iexact='DEPURADO')
        count = qs.count()
        if dry_run:
            return Response({'dry_run': True, 'to_delete': count}, status=status.HTTP_200_OK)
        # registrar historial por cada ioc por trazabilidad
        for ioc in qs.iterator():
            try:
                IocHistory.objects.create(ioc=ioc, action=f'PURGED AFTER AUDIT {audit_id}', user=request.user.username, comment=f'Purgado vía UI tras auditoría {audit_id} por {request.user.username}')
            except Exception:
                pass
        qs.delete()
        return Response({'detail': f'Purgados {count} IoCs', 'purged_count': count}, status=status.HTTP_200_OK)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db import transaction

from .models import IocEntry, IocHistory
from .utils import is_invalid_value


class BulkChangeStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user.username if request.user.is_authenticated else "system"

        new_state = request.data.get("new_state")
        if new_state not in ("BLOQUEADO", "DEPURADO"):
            return Response(
                {"detail": 'Estado inválido. Use "BLOQUEADO" o "DEPURADO".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------
        # 🔹 Cargar IoCs
        # -------------------------
        lines = []

        if "file" in request.FILES:
            f = request.FILES["file"]
            try:
                txt = f.read().decode("utf-8", errors="ignore")
            except Exception:
                f.seek(0)
                txt = b"".join(chunk for chunk in f.chunks()).decode("utf-8", errors="ignore")

            lines = [l.strip() for l in txt.splitlines() if l.strip()]
        else:
            data_lines = request.data.get("lines")
            if isinstance(data_lines, list):
                lines = [str(l).strip() for l in data_lines if str(l).strip()]
            else:
                return Response(
                    {"detail": "No se proporcionaron líneas o archivo."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if not lines:
            return Response(
                {"detail": "Lista de IoCs vacía."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------
        # 🔹 Normalizar y validar
        # -------------------------
        clean_values = []
        errors = []

        for v in set(lines):
            if is_invalid_value(v):
                errors.append({"value": v, "error": "invalid/placeholder"})
            else:
                clean_values.append(v)

        if not clean_values:
            return Response(
                {"updated_count": 0, "errors": errors},
                status=status.HTTP_200_OK
            )

        # -------------------------
        # 🔥 QUERY ÚNICA
        # -------------------------
        iocs = list(
            IocEntry.objects
            .filter(value__in=clean_values)
            .only("id", "value", "status")
        )

        found_map = {ioc.value: ioc for ioc in iocs}
        not_found = [v for v in clean_values if v not in found_map]

        to_update_ids = []
        history_objects = []
        updated = []

        for ioc in iocs:
            if ioc.status == new_state:
                updated.append({
                    "value": ioc.value,
                    "unchanged": True,
                    "old": ioc.status
                })
                continue

            old = ioc.status
            to_update_ids.append(ioc.id)

            history_objects.append(
                IocHistory(
                    ioc_id=ioc.id,
                    action=f"STATE_CHANGE {old} -> {new_state}",
                    user=user,
                    comment=f"Bulk update via UI by {user}"
                )
            )

            updated.append({
                "value": ioc.value,
                "old": old,
                "new": new_state
            })

        # -------------------------
        # 🚀 OPERACIONES MASIVAS
        # -------------------------
        with transaction.atomic():
            if to_update_ids:
                IocEntry.objects.filter(id__in=to_update_ids).update(status=new_state)

            if history_objects:
                IocHistory.objects.bulk_create(history_objects, batch_size=1000)

        return Response({
            "updated_count": len(to_update_ids),
            "updated": updated,
            "not_found": not_found,
            "errors": errors
        }, status=status.HTTP_200_OK)
    

# reemplaza o actualiza tu GenerarReporteView con esto 


class GenerarReporteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tipo = request.GET.get("tipo", "resumen")
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        fuente_filter = request.GET.get("fuente")
        

        if not inicio or not fin:
            return JsonResponse({"error": "Debes proporcionar 'inicio' y 'fin' (YYYY-MM-DD)."}, status=400)

        try:
            start_date = datetime.strptime(inicio, "%Y-%m-%d").date()
            end_date = datetime.strptime(fin, "%Y-%m-%d").date()
        except Exception:
            return JsonResponse({"error": "Formato de fecha inválido. Usa YYYY-MM-DD."}, status=400)

        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)

        qs = IocEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        if fuente_filter:
            qs = qs.filter(source__iexact=fuente_filter)

        total_period = qs.count()

        if total_period == 0:
            content = f"REPORTE Artemis\nDesde {start_date.isoformat()} Hasta {end_date.isoformat()}\n\nNo se encontraron indicadores en el rango especificado."
            return HttpResponse(content, content_type='text/plain; charset=utf-8')

        if tipo == "resumen":
            content = self._generar_resumen(qs, start_date, end_date, total_period)
        else:
            content = self._generar_detalle(qs, start_date, end_date)

        filename = f"reporte_artemis_{tipo}_{start_date.isoformat()}_{end_date.isoformat()}.txt"
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp

    def _generar_resumen(self, qs, start_date, end_date, total_period):
        lines = [
            f"REPORTE Artemis",
            f"Desde {start_date.isoformat()} Hasta {end_date.isoformat()}",
            f"Total periodo: {total_period} indicadores",
            ""
        ]

        by_source = qs.values('source').annotate(total=Count('id')).order_by('-total')

        for src_row in by_source:
            src = src_row.get('source') or 'Sin fuente'
            total = src_row.get('total', 0)

            lines.append(f"Fuente: {src}")
            lines.append(f"Total: {total} indicadores")
            lines.append("Herramientas")

            # IDs filtrados por fuente específica
            if src == 'Sin fuente':
                ioc_ids = list(qs.filter(source__isnull=True).values_list('id', flat=True))
            else:
                ioc_ids = list(qs.filter(source__iexact=src).values_list('id', flat=True))

            # Conteo por herramienta
            tool_counts = (
                IocTool.objects.filter(ioc_id__in=ioc_ids)
                .values('tool__name')
                .annotate(cnt=Count('ioc_id'))
                .order_by('-cnt')
            )

            # Conteo por herramienta + tipo de IOC
            tool_type_counts = (
                IocTool.objects.filter(ioc_id__in=ioc_ids)
                .select_related('ioc__ioc_type', 'tool')
                .values('tool__name', 'ioc__ioc_type__name')
                .annotate(cnt=Count('ioc_id'))
            )

            # Estructura: { "EDR (Crowdstrike)": { "IP": 1200, "URL": 40 } }
            tool_type_map = {}
            for row in tool_type_counts:
                tool_name = row['tool__name']
                ioc_type = row['ioc__ioc_type__name']
                cnt = row['cnt']

                tool_type_map.setdefault(tool_name, {})
                tool_type_map[tool_name][ioc_type] = cnt

            if not tool_counts:
                lines.append(f"  Sin herramienta: {total}")
            else:
                for t in tool_counts:
                    name = t.get('tool__name') or 'Sin herramienta'
                    cnt_total_tool = t.get('cnt', 0)

                    # Línea principal
                    lines.append(f"  {name}: {cnt_total_tool}")

                    # Subtipos (IP, DOMAIN, HASH, EMAIL, etc.)
                    if name in tool_type_map:
                        subtips = tool_type_map[name]
                        subtipo_line = "      " + ", ".join([f"{k}: {v}" for k, v in subtips.items()])
                        lines.append(subtipo_line)

                # IOC sin herramienta
                with_tool_ids = set(IocTool.objects.filter(ioc_id__in=ioc_ids).values_list('ioc_id', flat=True))
                no_tool_count = len([i for i in ioc_ids if i not in with_tool_ids])
                if no_tool_count:
                    lines.append(f"  Sin herramienta: {no_tool_count}")

            lines.append("")

        return "\n".join(lines)


    def _generar_detalle(self, qs, start_date, end_date):
        lines = [
            f"REPORTE Artemis - Detallado",
            f"Desde {start_date.isoformat()} Hasta {end_date.isoformat()}",
            "",
            f"{'Fuente':<20} {'Tipo':<15} {'Indicador':<35} {'Herramienta(s)':<40} {'Fecha creación':<20}",
            "-" * 150
        ]

        for i in qs.select_related('ioc_type').order_by('created_at'):
            fuente = i.source or "Sin fuente"
            tipo = i.ioc_type.name if getattr(i, 'ioc_type', None) else "Desconocido"
            indicador = i.value or "N/A"

            herramientas = ", ".join(
                i.tools.values_list('tool__name', flat=True)
            ) or "Sin herramienta"

            fecha = i.created_at.strftime("%Y-%m-%d %H:%M")

            lines.append(
                f"{fuente:<20} {tipo:<15} {indicador:<35} {herramientas:<40} {fecha:<20}"
            )

        return "\n".join(lines)

from django.http import HttpResponse
from zipfile import ZipFile
import io

class ExportIngestedByBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, batch_id):
        iocs = (
            IocEntry.objects
            .filter(upload_batch=batch_id)
            .select_related('ioc_type')
        )

        if not iocs.exists():
            return Response(
                {'detail': 'No hay IoCs para este lote'},
                status=404
            )

        buffer = io.BytesIO()

        with ZipFile(buffer, 'w') as zip_file:
            grouped = {}

            for ioc in iocs:
                tipo = ioc.ioc_type.name
                grouped.setdefault(tipo, []).append(ioc.value)

            for tipo, values in grouped.items():
                content = "\n".join(values) + "\n"
                zip_file.writestr(f"{tipo}.txt", content)

        buffer.seek(0)

        response = HttpResponse(
            buffer.read(),
            content_type='application/zip'
        )
        response['Content-Disposition'] = (
            'attachment; filename="iocs_ingestados.zip"'
        )
        response['Content-Length'] = buffer.tell()

        return response

from django.contrib.auth import authenticate, login, logout


from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect



def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        print("USERNAME:", username)
        print("PASSWORD:", password)

        user = authenticate(request, username=username, password=password)
        print("AUTH RESULT:", user)

        if user is not None:
            login(request, user)
            print("LOGIN OK")
            return redirect('/')
        else:
            print("LOGIN FAIL")
            return render(request, 'registration/login.html', {
                'error': 'Usuario o contraseña incorrectos'
            })

    return render(request, 'registration/login.html')


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'detail': 'Sesión cerrada'})



def login_page(request):
    return render(request, 'ioc_manager/login.html')

from django.contrib.auth import login

import json

def api_login(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = json.loads(request.body)
    user = authenticate(
        request,
        username=data.get('username'),
        password=data.get('password')
    )

    if user is None:
        return JsonResponse({'detail': 'Invalid credentials'}, status=401)

    login(request, user)
    return JsonResponse({'ok': True})

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('/login/')


