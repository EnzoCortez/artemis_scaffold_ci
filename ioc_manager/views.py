# views.py - Cleaned Refactored Version
import io
import os
import uuid
import logging
import zipfile
import hashlib
from datetime import datetime
from django.utils import timezone
from django.utils.encoding import smart_str
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.db import transaction
from django.db.models import Q, Count
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework import serializers as drf_serializers

from ioc_manager.services.ingestion_service import validate_and_ingest
from .utils import associate_iocs_with_allowed_tools_bulk, detect_ioc_type, validate_tool_accepts_ioc, remove_defanging, apply_defanging
from .models import (
    IocEntry,
    IocType,
    # IocHistory removed
    IocTool,
    Tool,

)
from .serializers import IocEntrySerializer

logger = logging.getLogger(__name__)

# --- Utils ---

def is_invalid_value(s):
    "Valores que consideramos inválidos / placeholders y que no deben guardarse."
    if s is None:
        return True
    s = str(s).strip()
    if s == '' or s == '—' or s == '-' or len(s) < 2:
        return True
    return False

# --- Views ---

@method_decorator(login_required(login_url='/login/'), name='dispatch')
class IndexView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        tools = Tool.objects.all().order_by('name')
        return render(request, 'ioc_manager/index.html', {'tools': tools})


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

        # 2️⃣ Validación, limpieza y desofuscación
        for line in lines:
            total += 1
            # Aplicar desofuscación antes de cualquier procesamiento
            cleaned_line = remove_defanging(line)
            if is_invalid_value(cleaned_line):
                skipped.append({'line': line, 'reason': 'invalid/placeholder'})
            else:
                clean_values.append(cleaned_line)

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

        # Cargar herramientas disponibles y sus reglas
        all_tools_qs = Tool.objects.prefetch_related('indicator_rules__ioc_type')
        all_tool_names = []
        tools_info = []

        for t in all_tools_qs:
            all_tool_names.append(t.name)
            compatible_types = [
                rule.ioc_type.name for rule in t.indicator_rules.all() if rule.can_ingest
            ]
            tools_info.append({
                "id": t.id,
                "name": t.name,
                "compatible_types": compatible_types
            })

        # 5️⃣ Clasificación final
        for value in clean_values:
            try:
                detected = detect_ioc_type(value)
            except Exception:
                detected = ''

            if not detected:
                skipped.append({'line': value, 'reason': 'No pudo detectar tipo (formato no soportado)'})
                continue
                
            # Si existe en BD Y ya tiene al menos una herramienta, es duplicado
            if value in existing_map and tools_map.get(existing_map[value].id):
                ioc = existing_map[value]
                duplicates.append({
                    'value': ioc.value,
                    'ioc_type': ioc.ioc_type.name if ioc.ioc_type else '',
                    'tools': tools_map.get(ioc.id, [])
                })
            else:
                # 🔒 VALIDACIÓN ESTRICTA: ¿Alguna herramienta soporta este IOC?
                supported_by_any = False
                for t_name in all_tool_names:
                    is_valid, _ = validate_tool_accepts_ioc(t_name, value)
                    if is_valid:
                        supported_by_any = True
                        break
                
                if not supported_by_any:
                    skipped.append({'line': value, 'reason': f'No soportado por ninguna herramienta ({detected})'})
                    continue

                new_items.append({
                    'value': value,
                    'detected_type': detected
                })

        # 6️⃣ Respuesta optimizada
        return Response({
            'tools_info': tools_info,
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
        
        # 🔹 Preload Tools names para validación
        from .models import Tool
        from .utils import validate_tool_accepts_ioc
        all_tool_names = list(Tool.objects.values_list('name', flat=True))

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

            # 🔒 VALIDACIÓN ESTRICTA: ¿Alguna herramienta soporta este IOC?
            supported_by_any = False
            for t_name in all_tool_names:
                is_valid, _ = validate_tool_accepts_ioc(t_name, value)
                if is_valid:
                    supported_by_any = True
                    break
            
            if not supported_by_any:
                errors.append({'value': value, 'error': f'No soportado por ninguna herramienta ({ioc_type.name})'})
                continue

            key = (ioc_type.id, value)

            if key in existing_map:
                existing.append(value)
                continue

            val_hash = hashlib.sha256(value.encode('utf-8')).hexdigest()
            to_create.append(
                IocEntry(
                    ioc_type=ioc_type,
                    value=value,
                    value_hash=val_hash,
                    created_by=user,
                    source=fuente,
                    upload_batch=batch_id
                )
            )
            inserted.append(value)

        # 🔹 Incrementar intentos para los duplicados
        if existing:
            from django.db.models import F
            IocEntry.objects.filter(value__in=existing).update(ingestion_attempts=F('ingestion_attempts') + 1)

        # 🔹 Inserción masiva
        IocEntry.objects.bulk_create(
            to_create,
            batch_size=1000
        )

        # 🔥 RECONSULTAR (ya con ID)
        created_iocs = list(
            IocEntry.objects.filter(upload_batch=batch_id)
            .select_related('ioc_type')
        )
        
        # 🔥 Asignar herramientas
        associate_iocs_with_allowed_tools_bulk(
            list(created_iocs),
            user=request.user
        )

        # 📋 Registrar lote en historial
        from .models import IocLoadBatch
        IocLoadBatch.objects.create(
            source=fuente,
            file_name=request.data.get('file_name') or request.data.get('filename') or '',
            total=len(items),
            inserted=len(created_iocs),
            duplicated=len(existing),
            rejected=len(errors),
            uploaded_by=request.user,
            batch_uuid=batch_id
        )

        return Response({
            'inserted_count': len(created_iocs),
            'existing_count': len(existing),
            'errors': errors,
            'batch_id': batch_id,
            'source': fuente
        }, status=200)


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
            .prefetch_related("tools")
            .only("value", "status", "ioc_type__name", "created_at", "ingestion_attempts")
        )

        # 🔹 Respuesta liviana (NO SERIALIZER)
        results = [
            {
                "id": ioc.id,
                "value": ioc.value,
                "status": ioc.status,
                "ioc_type": ioc.ioc_type.name if ioc.ioc_type else "",
                "created_at": ioc.created_at.isoformat() if ioc.created_at else None,
                "ingestion_attempts": getattr(ioc, "ingestion_attempts", 0),
                "tools": [t.tool.name for t in ioc.tools.all() if t.tool]
            }
            for ioc in qs
        ]

        return Response({"results": results}, status=status.HTTP_200_OK)

class AssignToolManualView(APIView):
    """
    POST /api/iocs/assign-tool-manual/
    Body:
    {
        "value": "ioc_value",
        "tool_name": "WAF",
        "fuente": "IBM"
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        value = request.data.get("value", "").strip()
        tool_name = request.data.get("tool_name", "").strip()
        fuente = request.data.get("fuente", "Manual").strip()

        if not value or not tool_name:
            return Response({"detail": "Falta value o tool_name"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ioc = IocEntry.objects.get(value=value)
        except IocEntry.DoesNotExist:
            return Response({"detail": "El IoC no existe en la base de datos"}, status=status.HTTP_404_NOT_FOUND)

        from .models import Tool
        tool, _ = Tool.objects.get_or_create(name=tool_name)

        if not validate_tool_accepts_ioc(tool, ioc):
            return Response({"detail": f"La herramienta {tool.name} no acepta IoCs tipo {ioc.ioc_type.name}"}, status=status.HTTP_400_BAD_REQUEST)

        from .models import IocTool
        if IocTool.objects.filter(ioc=ioc, tool=tool).exists():
            return Response({"detail": "El IoC ya está asignado a esta herramienta"}, status=status.HTTP_400_BAD_REQUEST)

        IocTool.objects.create(
            ioc=ioc,
            tool=tool,
            status='Ingestado',
            detail=f'Asignación manual. Fuente: {fuente}'
        )

        return Response({"detail": "Herramienta asignada correctamente"}, status=status.HTTP_200_OK)


class AssignToolBulkView(APIView):
    """
    POST /api/iocs/assign-tool-bulk/
    Body:
    {
        "assignments": [
            {"value": "1.1.1.1", "tool_id": 1},
            {"value": "evil.com", "tool_id": 2}
        ]
    }
    Asigna múltiples IoCs a múltiples herramientas sin reingestar.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        assignments = request.data.get("assignments", [])
        
        if not assignments:
            return Response({"detail": "Faltan assignments"}, status=status.HTTP_400_BAD_REQUEST)

        values = list(set([a.get("value") for a in assignments if a.get("value")]))
        tool_ids = list(set([a.get("tool_id") for a in assignments if a.get("tool_id")]))

        # Obtener IoCs existentes
        iocs = IocEntry.objects.filter(value__in=values).select_related("ioc_type")
        ioc_map = {ioc.value: ioc for ioc in iocs}

        # Obtener herramientas
        tools = Tool.objects.filter(id__in=tool_ids)
        tool_map = {tool.id: tool for tool in tools}

        # Obtener relaciones existentes para evitar duplicados
        existing_links = set(
            IocTool.objects.filter(
                ioc__value__in=values,
                tool__in=tools
            ).values_list("ioc__value", "tool_id")
        )

        assigned = 0
        skipped = 0
        errors = []

        bulk_create_list = []
        for item in assignments:
            val = item.get("value")
            t_id = item.get("tool_id")
            
            ioc = ioc_map.get(val)
            tool = tool_map.get(t_id)

            if not ioc or not tool:
                errors.append({"value": val, "reason": f"IoC o Tool (ID: {t_id}) no encontrados"})
                continue

            if (val, tool.id) in existing_links:
                skipped += 1
                continue

            # Validar compatibilidad tipo-herramienta
            is_valid, reason = validate_tool_accepts_ioc(tool.name, val)
            if not is_valid:
                errors.append({"value": val, "reason": f"No compatible con {tool.name}: {reason}"})
                continue

            bulk_create_list.append(IocTool(
                ioc=ioc,
                tool=tool,
                status='Ingestado',
                detail=f'Asignación masiva (matriz) por {request.user.username}'
            ))
            # Agregar temporalmente a existing_links para evitar duplicados dentro del mismo request
            existing_links.add((val, tool.id))
            assigned += 1

        if bulk_create_list:
            IocTool.objects.bulk_create(bulk_create_list)

        return Response({
            "assigned": assigned,
            "skipped": skipped,
            "errors": errors,
            "detail": f"Asignados: {assigned}, Omitidos: {skipped}, Errores: {len(errors)}"
        }, status=status.HTTP_200_OK)

class IocListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    DEFAULT_PAGE_SIZE = 50

    def get(self, request):
        q = request.query_params.get("search", "").strip()

        qs = (
            IocEntry.objects
            .select_related("ioc_type")
            .prefetch_related("tools")
            .order_by("-ingestion_attempts", "-created_at")
        )

        type_filter = request.query_params.get("type", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        date_start = request.query_params.get("date_start")
        date_end = request.query_params.get("date_end")

        if q:
            qs = qs.filter(
                Q(value__icontains=q) |
                Q(ioc_type__name__icontains=q)
            )

        if type_filter:
            qs = qs.filter(ioc_type__name__iexact=type_filter)
            
        if status_filter:
            qs = qs.filter(status__iexact=status_filter)

        if date_start:
            try:
                dt_start = datetime.strptime(date_start, "%Y-%m-%d")
                current_tz = timezone.get_current_timezone()
                dt_start = timezone.make_aware(datetime.combine(dt_start, datetime.min.time()), current_tz)
                qs = qs.filter(created_at__gte=dt_start)
            except ValueError:
                pass

        if date_end:
            try:
                dt_end = datetime.strptime(date_end, "%Y-%m-%d")
                current_tz = timezone.get_current_timezone()
                dt_end = timezone.make_aware(datetime.combine(dt_end, datetime.max.time()), current_tz)
                qs = qs.filter(created_at__lte=dt_end)
            except ValueError:
                pass

        # Paginación
        total_count = qs.count()
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", self.DEFAULT_PAGE_SIZE)), 1), 200)
        except (ValueError, TypeError):
            page_size = self.DEFAULT_PAGE_SIZE

        import math
        total_pages = max(math.ceil(total_count / page_size), 1)
        offset = (page - 1) * page_size
        page_qs = qs[offset:offset + page_size]

        serializer = IocEntrySerializer(page_qs, many=True)
        return Response({
            "results": serializer.data,
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }, status=status.HTTP_200_OK)


import csv

class ExportCsvStrategyView(APIView):
    """
    Exportación Universal a CSV usando Patrón Strategy (XP).
    Recibe una lista de objetos y los convierte a CSV.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        headers = request.data.get('headers', [])
        filename = request.data.get('filename', 'export.csv')

        if not items:
            return Response({'detail': 'No hay items para exportar'}, status=400)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        
        if headers:
            writer.writerow(headers)
        elif items and isinstance(items[0], dict):
            headers = list(items[0].keys())
            writer.writerow(headers)

        for item in items:
            if isinstance(item, dict):
                writer.writerow([item.get(h, '') for h in headers])
            else:
                writer.writerow([item])

        return response


class ExportClassifiedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        filename_prefix = request.data.get('filename_prefix', 'iocs').strip()
        defang = request.data.get('defang', False)
        
        # Sanitize filename (remove paths and extension)
        filename_prefix = os.path.basename(filename_prefix).rsplit('.', 1)[0]
        if not filename_prefix:
            filename_prefix = 'iocs'

        if not items or not isinstance(items, list):
            return Response({'detail': 'No items provided'}, status=400)

        # Classification logic
        grouped = {}
        for item in items:
            val = item.get('value') if isinstance(item, dict) else str(item)
            if not val:
                continue
            
            # Use detected_type if provided, else detect
            detected_type = item.get('detected_type') if isinstance(item, dict) else None
            if not detected_type:
                detected_type = detect_ioc_type(val) or 'Desconocido'

            if detected_type.lower() == 'hash':
                from .utils import detect_hash_algorithm
                algo = detect_hash_algorithm(val)
                if algo:
                    detected_type = f"Hash-{algo.upper()}"

            grouped.setdefault(detected_type, []).append(val)

        # Create ZIP
        buffer = io.BytesIO()
        date_str = timezone.now().strftime("%d-%m-%Y")
        # Replace underscores with hyphens in prefix
        filename_prefix = filename_prefix.replace("_", "-")

        with zipfile.ZipFile(buffer, 'w') as zf:
            combined_hashes = []
            for ioc_type, values in grouped.items():
                # Aplicar defanging si está activado (excepto hashes)
                if defang:
                    values = [apply_defanging(v, ioc_type) for v in values]
                content = "\n".join(values)
                fname = f"{filename_prefix}-bloqueo-de-ioc-{date_str}-{ioc_type}.txt"
                zf.writestr(fname, content)

                if ioc_type.upper() in ("HASH-MD5", "HASH-SHA256"):
                    combined_hashes.extend(values)
            
            if combined_hashes:
                content_combined = "\n".join(combined_hashes)
                fname_combined = f"{filename_prefix}-bloqueo-de-ioc-{date_str}-Hash-Combined.txt"
                zf.writestr(fname_combined, content_combined)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename_prefix}-classified.zip"'
        return response


class ExportIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _build_txt_response(self, queryset, filename, defang=False):
        def line_iterator():
            for value in queryset.iterator(chunk_size=1000):
                out = apply_defanging(value) if defang else value
                yield f"{smart_str(out)}\n"

        response = HttpResponse(
            line_iterator(),
            content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def get(self, request):
        batch = request.GET.get("batch")
        defang = request.GET.get("defang", "false").lower() == "true"

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
        return self._build_txt_response(values, "iocs_ingestados.txt", defang=defang)

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

        defang = request.data.get('defang', False)

        qs = (
            IocEntry.objects
            .filter(value__in=cleaned)
            .only("value")
            .order_by("value")
            .values_list("value", flat=True)
        )

        return self._build_txt_response(qs, "iocs_ingestados.txt", defang=defang)


class ExportNotIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('items', [])
        defang = request.data.get('defang', False)
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
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for ioc_type, values in classified.items():
                if defang:
                    values = [apply_defanging(v, ioc_type) for v in values]
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


class ValidateAndIngestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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


class ChangeIocStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        if pk is None:
            pk = request.data.get('ioc_id')

        try:
            ioc = IocEntry.objects.get(pk=pk)
        except IocEntry.DoesNotExist:
            return Response({'detail': 'IOC no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        new_state = request.data.get('new_state') or request.data.get('state')
        if new_state not in ['BLOQUEADO', 'DEPURADO']:
             return Response({'detail': 'Estado inválido'}, status=status.HTTP_400_BAD_REQUEST)
        
        old_state = ioc.status
        if old_state == new_state:
             return Response({'detail': 'El estado ya es el solicitado', 'status': new_state})

        ioc.status = new_state
        ioc.save()

        ioc.status = new_state
        ioc.save()

        # History logging removed (IocHistory model deleted)
        
        return Response({'detail': 'Estado actualizado', 'status': new_state})





class PurgeApiSerializer(drf_serializers.Serializer):
    audit_id = drf_serializers.IntegerField(required=False, allow_null=True)
    dry_run = drf_serializers.BooleanField(default=False)


class PurgeApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        # Support payload via body or URL pk (if logic requires pk to be audit_id?)
        # User error: /api/purge/:1 -> 500. 
        # CAUTION: 'pk' here probably refers to AUDIT ID based on context "purge/:1".
        
        data = request.data.copy()
        if pk:
            data['audit_id'] = pk
            
        serializer = PurgeApiSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        audit_id = serializer.validated_data.get('audit_id')
        dry_run = serializer.validated_data['dry_run']
        
        audit_id = serializer.validated_data.get('audit_id')
        dry_run = serializer.validated_data['dry_run']
        
        # Audio logic removed (History model deleted)
 

        qs = IocEntry.objects.filter(status__iexact='DEPURADO')
        count = qs.count()
        if dry_run:
            return Response({'dry_run': True, 'to_delete': count}, status=status.HTTP_200_OK)
            
        # 1. GENERAR REPORTE TXT MEJORADO
        now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        user_str = request.user.username

        lines = [
            f"REPORTE DE ELIMINACION DE IOCs (Estado DEPURADO)",
            f"===========================================================================================================",
            f"Fecha de Ejecución: {now_str}",
            f"Ejecutado por:      {user_str}",
            f"===========================================================================================================",
            f"",
            f"{'IOC (Valor)':<68} | {'Tipo':<15} | {'Fuente':<20}",
            f"{'-'*68}-+-{'-'*15}-+-{'-'*20}"
        ]

        # Obtener datos antes de borrar (optimizando memoria)
        to_delete_qs = qs.values_list('value', 'ioc_type__name', 'source', 'id')
        
        # Guardar IDs para borrar
        ids_to_delete = []
        
        for val, itype, src, iid in to_delete_qs:
             # Truncate source if too long to maintain alignment
             src_clean = (src or 'N/A')[:20]
             itype_clean = (itype or 'N/A')[:15]
             # Usar relleno de puntos (.) para guiar la vista en valores cortos
             lines.append(f"{val:.<68} | {itype_clean:<15} | {src_clean:<20}")
             ids_to_delete.append(iid)

        total_purged = len(ids_to_delete)
        
        lines.append(f"{'-'*68}-+-{'-'*15}-+-{'-'*20}")
        lines.append(f"Total registros eliminados: {total_purged}")
        lines.append(f"")
        lines.append(f"*** FIN DEL REPORTE ***")
        lines.append(f"Nota: Este archivo es un registro estático generado por el sistema Artemis.")

        # 2. BORRAR (Sin crear historial en DB)
        if ids_to_delete:
             # Borrar en lotes
             batch_size = 1000
             for i in range(0, len(ids_to_delete), batch_size):
                 chunk = ids_to_delete[i:i + batch_size]
                 IocEntry.objects.filter(id__in=chunk).delete()

        # 3. RETORNAR ARCHIVO
        report_content = "\n".join(lines)
        filename = f"reporte_eliminacion_{timezone.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        response = HttpResponse(report_content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Importante: Exponer header para que JS pueda leer nombre si fuera necesario (aunque browser maneja attachment)
        return response


class BulkChangeStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user if request.user.is_authenticated else None

        new_state = request.data.get("new_state")
        if new_state not in ("BLOQUEADO", "DEPURADO"):
            return Response(
                {"detail": 'Estado inválido. Use "BLOQUEADO" o "DEPURADO".'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        clean_values = []
        errors = []

        for v in set(lines):
            cleaned_v = remove_defanging(v)
            if is_invalid_value(cleaned_v):
                errors.append({"value": cleaned_v, "error": "invalid/placeholder"})
            else:
                clean_values.append(cleaned_v)

        if not clean_values:
            return Response(
                {"updated_count": 0, "errors": errors},
                status=status.HTTP_200_OK
            )

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

            old = ioc.status
            to_update_ids.append(ioc.id)

            # History object creation removed


            updated.append({
                "value": ioc.value,
                "old": old,
                "new": new_state
            })

        with transaction.atomic():
            if to_update_ids:
                IocEntry.objects.filter(id__in=to_update_ids).update(status=new_state)

        # IocHistory bulk create removed

        return Response({
            "updated_count": len(to_update_ids),
            "not_found": not_found,
            "errors": errors
        }, status=status.HTTP_200_OK)


class GenerarReporteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tipo = request.GET.get("tipo", "resumen")
        inicio = request.GET.get("inicio")
        fin = request.GET.get("fin")
        fuente_filter = request.GET.get("fuente")
        fuente_custom = request.GET.get("fuente_custom") # Nuevo param custom
        ioc_type_filter = request.GET.get("ioc_type")    # Nuevo param type

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
        
        # 1. Filtro Fuente
        if fuente_filter:
            if fuente_filter.lower() == "otro":
                if fuente_custom:
                    qs = qs.filter(source__iexact=fuente_custom.strip())
                else:
                    # Excluir fuentes estándar
                    STANDARD_SOURCES = ["IBM", "Cisco", "Kaspersky", "Pichincha"]
                    qs = qs.exclude(source__in=STANDARD_SOURCES)
            else:
                qs = qs.filter(source__iexact=fuente_filter)
        
        # 2. Filtro Tipo IOC
        if ioc_type_filter:
            qs = qs.filter(ioc_type__name__iexact=ioc_type_filter)

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
        sep_main = "=" * 50
        sep_sub = "-" * 50
        
        lines = [
            sep_main,
            f" REPORTE Artemis",
            f" Desde {start_date.isoformat()} Hasta {end_date.isoformat()}",
            f" Total periodo: {total_period} indicadores",
            sep_main,
            ""
        ]

        by_source = qs.values('source').annotate(total=Count('id')).order_by('-total')

        for src_row in by_source:
            src = src_row.get('source') or 'Sin fuente'
            total = src_row.get('total', 0)

            lines.append(sep_sub)
            lines.append(f" Fuente: {src}")
            lines.append(f" Total: {total} indicadores")
            lines.append(sep_sub)
            lines.append(" Herramientas y Clasificación:")

            # IDs filtrados por fuente específica
            if src == 'Sin fuente':
                ioc_ids = list(qs.filter(Q(source__isnull=True) | Q(source='')).values_list('id', flat=True))
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
            f"{'Fuente':<30} {'Tipo':<15} {'Indicador':<70} {'Herramienta(s)':<55} {'Fecha creación':<20}",
            "-" * 195
        ]

        # Optimización: prefetch de tools -> tool para evitar N+1
        qs = qs.select_related('ioc_type').prefetch_related('tools__tool').order_by('created_at')

        for i in qs:
            fuente = (i.source or "Sin fuente")[:29]
            tipo = (i.ioc_type.name if getattr(i, 'ioc_type', None) else "Desconocido")[:14]
            # Hashtags max length 64 (SHA256), URLs can be long
            indicador = (i.value or "N/A")[:69]

            # Uso de la relación precargada (python-side)
            tool_names = [t.tool.name for t in i.tools.all() if t.tool]
            herramientas = (", ".join(tool_names) or "Sin herramienta")[:54]

            from django.utils import timezone
            fecha_local = timezone.localtime(i.created_at) if i.created_at else None
            fecha = fecha_local.strftime("%Y-%m-%d %H:%M") if fecha_local else "Desconocida"

            lines.append(
                f"{fuente:<30} {tipo:<15} {indicador:<70} {herramientas:<55} {fecha:<20}"
            )

        return "\n".join(lines)


class ExportIngestedByBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, batch_id):
        defang = request.GET.get("defang", "false").lower() == "true"
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

        with zipfile.ZipFile(buffer, 'w') as zip_file:
            grouped = {}

            for ioc in iocs:
                tipo = ioc.ioc_type.name
                grouped.setdefault(tipo, []).append(ioc.value)

            for tipo, values in grouped.items():
                if defang:
                    values = [apply_defanging(v, tipo) for v in values]
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


# --- Auth Views ---

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            return render(request, 'registration/login.html', {
                'error': 'Usuario o contraseña incorrectos'
            })

    return render(request, 'registration/login.html')


def logout_view(request):
    logout(request)
    return redirect('/login/')

# ==========================================================
# CSV CLEANER VIEW
# ==========================================================






# ==========================================================
# REPORT VIEWS ENHANCEMENTS (TICKET 7 & TXT ANALISIS)
# ==========================================================
from django.db.models import Count

class ReportesTotalesHerramientasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from datetime import datetime
        
        date_start = request.query_params.get("date_start")
        date_end = request.query_params.get("date_end")

        ioc_filter = Q()
        
        if date_start:
            try:
                dt_start = datetime.strptime(date_start, "%Y-%m-%d")
                current_tz = timezone.get_current_timezone()
                dt_start = timezone.make_aware(datetime.combine(dt_start, datetime.min.time()), current_tz)
                ioc_filter &= Q(iocs__ioc__created_at__gte=dt_start)
            except ValueError:
                pass

        if date_end:
            try:
                dt_end = datetime.strptime(date_end, "%Y-%m-%d")
                current_tz = timezone.get_current_timezone()
                dt_end = timezone.make_aware(datetime.combine(dt_end, datetime.max.time()), current_tz)
                ioc_filter &= Q(iocs__ioc__created_at__lte=dt_end)
            except ValueError:
                pass

        tools = Tool.objects.annotate(ioc_count=Count('iocs', filter=ioc_filter)).order_by('-ioc_count')
        
        # Build text report
        lines = []
        lines.append("="*50)
        lines.append(" REPORTE TOTALES POR HERRAMIENTA")
        if date_start or date_end:
            lines.append(f" Rango: {date_start or 'Ilimitado'} al {date_end or 'Presente'}")
        lines.append("="*50)
        lines.append("")
        
        for tool in tools:
            lines.append(f" Herramienta: {tool.name}")
            lines.append(f" Total Indicadores: {tool.ioc_count}")
            lines.append("-" * 50)
            
        content = "\n".join(lines)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="reporte_totales_herramientas.txt"'
        return response

class ReportesAnalisisTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)
            
        try:
            raw = file_obj.read()
            text = raw.decode('utf-8', errors='ignore')
        except Exception:
            return Response({'error': 'Invalid file encoding'}, status=400)
            
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        lines = [remove_defanging(l) for l in raw_lines]
        
        existing = IocEntry.objects.filter(value__in=lines).select_related('ioc_type').prefetch_related('tools')
        existing_map = {ioc.value.lower(): ioc for ioc in existing}
        
        found_count = 0
        not_found_count = 0
        
        # Calcular ancho dinámico para la columna 'Indicador' basado en el más largo
        max_ioc_len = max([len(l) for l in lines] + [45]) if lines else 45
        
        detail_lines = []
        header = f"| {'#'.ljust(6)} | {'Estado'.ljust(14)} | {'Indicador'.ljust(max_ioc_len)} | {'Tipo'.ljust(12)} | {'Herramientas'.ljust(35)} | {'Fecha'.ljust(16)} |"
        divisor = "-" * len(header)
        
        detail_lines.append(divisor)
        detail_lines.append(header)
        detail_lines.append(divisor)
        
        for idx, line in enumerate(lines, 1):
            val_lower = line.lower()
            idx_str = str(idx).ljust(6)
            
            line_str = line.ljust(max_ioc_len)
            
            if val_lower in existing_map:
                ioc = existing_map[val_lower]
                tool_names = [t.tool.name for t in ioc.tools.all() if t.tool]
                tools_raw = ", ".join(tool_names) if tool_names else "Ninguna"
                if len(tools_raw) > 35:
                    tools_raw = tools_raw[:32] + "..."
                tools_str = tools_raw.ljust(35)
                
                tipo_raw = ioc.ioc_type.name if ioc.ioc_type else "Desconocido"
                if len(tipo_raw) > 12:
                    tipo_raw = tipo_raw[:9] + "..."
                tipo = tipo_raw.ljust(12)
                
                try:
                    dt = timezone.localtime(ioc.created_at).strftime('%Y-%m-%d %H:%M') if ioc.created_at else 'Desconocida'
                except Exception:
                    dt = str(ioc.created_at)[:16]
                date_str = dt.ljust(16)
                
                estado = "INGESTADO".ljust(14)
                
                detail_lines.append(f"| {idx_str} | {estado} | {line_str} | {tipo} | {tools_str} | {date_str} |")
                found_count += 1
            else:
                estado = "NO INGESTADO".ljust(14)
                detail_lines.append(f"| {idx_str} | {estado} | {line_str} | {'-'.ljust(12)} | {'-'.ljust(35)} | {'-'.ljust(16)} |")
                not_found_count += 1
        
        detail_lines.append(divisor)
        
        out_lines = []
        out_lines.append("=" * len(header))
        out_lines.append(" REPORTE DE ANALISIS DE INDICADORES CARGADOS")
        out_lines.append("=" * len(header))
        out_lines.append(f"Total procesados en TXT: {len(lines)}")
        out_lines.append(f"Encontrados (Ingestados): {found_count}")
        out_lines.append(f"No encontrados: {not_found_count}")
        out_lines.append("")
        
        out_lines.extend(detail_lines)
        
        content = "\n".join(out_lines)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="reporte_analisis_txt.txt"'
        return response
