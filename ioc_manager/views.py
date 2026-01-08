# views.py - versión corregida y completa
import io
import uuid
import logging


from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.encoding import smart_str
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .utils import detect_ioc_type

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Count

from datetime import datetime



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
    CHUNK_SIZE = 500

    def post(self, request, format=None):
        data = request.data
        items = data.get("items", [])
        fuente = data.get("fuente") or data.get("source") or "Desconocida"

        if not isinstance(items, list):
            return Response(
                {"detail": "items debe ser una lista"},
                status=status.HTTP_400_BAD_REQUEST
            )

        batch_id = str(uuid.uuid4())
        user = request.user if request.user.is_authenticated else None

        inserted = []
        existing = []
        errors = []

        # 1️⃣ Normalizar valores
        values = []
        for item in items:
            if isinstance(item, dict):
                v = item.get("value")
            else:
                v = item

            if not v or str(v).strip() in {"", "-", "--", "—"}:
                continue

            values.append(str(v).strip())

        if not values:
            return Response(
                {"detail": "No se encontraron IoCs válidos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2️⃣ Buscar existentes (O(1))
        existing_qs = (
            IocEntry.objects
            .filter(value__in=values)
            .only("value")
        )
        existing_map = {i.value for i in existing_qs}

        # 3️⃣ Preparar nuevos
        new_objects = []
        for value in values:
            if value in existing_map:
                existing.append(value)
                continue

            detected_type = detect_ioc_type(value)
            ioc_type = (
                IocType.objects.filter(name__iexact=detected_type).first()
                if detected_type else None
            )

            new_objects.append(
                IocEntry(
                    value=value,
                    ioc_type=ioc_type,
                    source=fuente,
                    upload_batch=batch_id,
                    created_by=user
                )
            )

        # 4️⃣ Insertar en bulk
        try:
            with transaction.atomic():
                for i in range(0, len(new_objects), self.CHUNK_SIZE):
                    IocEntry.objects.bulk_create(
                        new_objects[i:i + self.CHUNK_SIZE]
                    )

                inserted = [o.value for o in new_objects]

                # 5️⃣ Crear historial (ya con PK)
                created_iocs = IocEntry.objects.filter(upload_batch=batch_id)

                histories = [
                    IocHistory(
                        ioc=ioc,
                        action="INGESTADO",
                        user=user.username if user else "system"
                    )
                    for ioc in created_iocs
                ]

                IocHistory.objects.bulk_create(histories)

        except Exception as e:
            return Response(
                {"detail": "Error durante carga masiva", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "inserted": inserted,
                "existing": existing,
                "errors": errors,
                "batch_id": batch_id,
                "source": fuente
            },
            status=status.HTTP_200_OK
        )
        
        
        
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


class ExportDuplicatesTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        POST /api/export/duplicates/  with JSON { items: [...] }
        Devuelve en un TXT las entradas de 'items' que EXISTEN en la DB (es decir: coincidencias/duplicados).
        Útil cuando frontend tiene la lista 'existing' y quiere descargar el TXT de duplicados.
        """
        items = request.data.get('items', [])
        if not isinstance(items, (list, tuple)):
            return Response({'detail': 'items debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)
        items_clean = [str(i).strip() for i in items if str(i).strip()]
        if not items_clean:
            content = ""
            resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
            resp['Content-Disposition'] = 'attachment; filename="iocs_duplicados.txt"'
            return resp
        existing = list(IocEntry.objects.filter(value__in=items_clean).values_list('value', flat=True))
        content = "\n".join(existing) + ("\n" if existing else "")
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="iocs_duplicados.txt"'
        return resp

class ExportNotIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        POST /api/export/not-ingested/  with JSON { items: [...] }
        Devuelve los items que NO están en la DB (no-ingestados) — opción útil si quieres ese archivo.
        """
        items = request.data.get('items', [])
        if not isinstance(items, (list, tuple)):
            return Response({'detail': 'items debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)
        items_clean = [str(i).strip() for i in items if str(i).strip()]
        if not items_clean:
            content = ""
            resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
            resp['Content-Disposition'] = 'attachment; filename="iocs_no_ingestados.txt"'
            return resp
        existing = set(IocEntry.objects.filter(value__in=items_clean).values_list('value', flat=True))
        not_ingested = [i for i in items_clean if i not in existing]
        content = "\n".join(not_ingested) + ("\n" if not_ingested else "")
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="iocs_no_ingestados.txt"'
        return resp

""" 
class ChangeIocStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ioc_id = request.data.get('ioc_id')
        new_state = request.data.get('new_state')
        user = request.user.username if request.user.is_authenticated else 'system'
        if new_state not in ('BLOQUEADO', 'DEPURADO'):
            return Response({'detail': 'Estado inválido'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ioc = IocEntry.objects.get(id=ioc_id)
        except IocEntry.DoesNotExist:
            return Response({'detail': 'IoC no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        old = ioc.status
        ioc.status = new_state
        ioc.save(update_fields=['status'])
        try:
            IocHistory.objects.create(ioc=ioc, action=f'STATE_CHANGE {old} -> {new_state}', user=user)
        except Exception:
            pass
        return Response({'detail': 'Estado actualizado'}, status=status.HTTP_200_OK)

"""




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



