# views.py - versión corregida y completa
import io
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.encoding import smart_str
from django.db import transaction
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAdminUser

import uuid

from datetime import datetime, date
from django.db.models import Count
from .models import IocEntry, IocTool
from rest_framework.authentication import TokenAuthentication

from .models import IocEntry, IocType, IocHistory
import logging

from django.utils.dateparse import parse_date
from .models import IocEntry, IocTool, Tool, Firewall, FirewallIocType

from django.utils import timezone
from datetime import timezone as dt_timezone

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

# Intentamos importar la función de detección más robusta si existe en utils.py


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

        # leer con tolerancia de encoding
        try:
            raw = file_obj.read()
            text = raw.decode('utf-8', errors='ignore')
        except Exception:
            try:
                file_obj.seek(0)
                text = b''.join(chunk for chunk in file_obj.chunks()).decode('utf-8', errors='ignore')
            except Exception as e:
                return Response({'detail': f'Error leyendo archivo: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        lines = [l.rstrip('\r\n') for l in text.splitlines()]
        duplicates = []
        new_items = []
        skipped = []
        total = 0

        # preload ioc types for minor optimization
        ioc_type_map = {it.name.lower(): it for it in IocType.objects.all()} if hasattr(IocType, 'objects') else {}

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                # ignorar líneas vacías
                continue
            total += 1
            if is_invalid_value(line):
                skipped.append({'line': line, 'reason': 'invalid/placeholder'})
                continue

            # detect type heuristically
            try:
                detected = detect_ioc_type_py(line)
            except Exception:
                detected = None

            # Attempt to find existing IoC by value (value uniqueness assumed)
            existing = IocEntry.objects.filter(value=line).select_related('ioc_type').first()
            if existing:
                # obtener herramientas asociadas a este IOC si existe modelo IocTool
                tools = []
                try:
                    tool_qs = IocTool.objects.filter(ioc=existing).select_related('tool')
                    tools = [t.tool.name for t in tool_qs if getattr(t, 'tool', None) and getattr(t.tool, 'name', None)]
                except Exception:
                    # si no existe IocTool o relación distinta,ignorar
                    tools = []

                duplicates.append({
                    'value': smart_str(existing.value),
                    'ioc_type': existing.ioc_type.name if getattr(existing, 'ioc_type', None) else (detected or ''),
                    'tools': tools
                })
            else:
                new_items.append({'value': smart_str(line), 'detected_type': detected or ''})

        result = {
            'duplicates': duplicates,
            'new': new_items,
            'skipped': skipped,
            'summary': {'total_lines_processed': total, 'duplicates': len(duplicates), 'new': len(new_items), 'skipped': len(skipped)}
        }
        return Response(result, status=status.HTTP_200_OK)


class LoadNewIocsView(APIView):
    #authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, format=None):
        """
        Recibe JSON: { items: [{value, type}? ...], fuente: 'IBM' }
        - Crea un batch_id
        - Marca los nuevos registros con upload_batch=batch_id y source=fuente
        Respuesta: { inserted: [...], existing: [...], errors: [...], batch_id: '...' }
        """
        data = request.data
        items = data.get('items', [])
        fuente = data.get('fuente') or data.get('source') or None

        if not isinstance(items, (list, tuple)):
            return Response({'detail': 'items debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)

        batch_id = str(uuid.uuid4())
        user = request.user if request.user.is_authenticated else None

        inserted = []
        existing = []
        errors = []

        with transaction.atomic():
            for item in items:
                if isinstance(item, dict):
                    value = item.get('value')
                    type_name = item.get('type') or item.get('detected_type')
                else:
                    value = item
                    type_name = None

                if not value or str(value).strip() in ['', '—', '-', '--']:
                    errors.append({'value': value, 'error': 'Valor inválido/placeholder'})
                    continue
                value = str(value).strip()

                # resolver ioc_type si se puede
                ioc_type_obj = None
                if type_name:
                    ioc_type_obj = IocType.objects.filter(name__iexact=type_name).first()
                if not ioc_type_obj:
                    # intentar deducción simple 
                    #from .utils import detect_ioc_type_py
                    detected = detect_ioc_type_py(value)
                    if detected:
                        ioc_type_obj = IocType.objects.filter(name__iexact=detected).first()

                try:
                    
                    # Convertir a texto seguro
                    value = str(value)
                    if value.startswith("[object Object]"):
                        errors.append({'value': value, 'error': 'Valor inválido: objeto en vez de texto'})
                        continue

                    # Asegurar que source y batch se registren correctamente
                    defaults = {
                        'created_by': user,
                        'source': fuente or 'Desconocida',
                        'upload_batch': batch_id
                    }
                    if ioc_type_obj:
                        obj, created = IocEntry.objects.get_or_create(
                            ioc_type=ioc_type_obj,
                            value=value,
                            defaults={'created_by': user, 'source': fuente, 'upload_batch': batch_id}
                        )
                    else:
                        # si por alguna razón no tenemos ioc_type, intentamos sin FK (si tu modelo lo permite)
                        obj, created = IocEntry.objects.get_or_create(
                            value=value,
                            defaults={'created_by': user, 'source': fuente, 'upload_batch': batch_id}
                        )
                    if created:
                        inserted.append(value)
                        try:
                            IocHistory.objects.create(ioc=obj, action='INGESTADO', user=request.user.username if request.user.is_authenticated else 'system')
                        except Exception:
                            pass
                    else:
                        existing.append(value)
                except Exception as e:
                    errors.append({'value': value, 'error': str(e)})

        return Response({'inserted': inserted, 'existing': existing, 'errors': errors, 'batch_id': batch_id, 'source': fuente}, status=status.HTTP_200_OK)


class IocListView(APIView):
    """
    GET /api/iocs/?search=...  -> devuelve lista de iocs (serializer)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = IocEntry.objects.all().order_by('-created_at')

        # soporte búsqueda por valor, por tipo (ioc_type.name) o por herramienta (si existe relación)
        q = request.query_params.get('search') or request.GET.get('search')
        if q:
            try:
                # intentamos filtrar por las tres fuentes (value, ioc_type, herramientas)
                qs = qs.filter(
                    Q(value__icontains=q) |
                    Q(ioc_type__name__icontains=q) |
                    Q(ioctool__tool__name__icontains=q)  # intenta join con IocTool -> Tool
                ).distinct().order_by('-created_at')
            except Exception:
                # fallback simple: solo value / ioc_type
                qs = qs.filter(
                    Q(value__icontains=q) |
                    Q(ioc_type__name__icontains=q)
                ).distinct().order_by('-created_at')

        serializer = IocEntrySerializer(qs, many=True)
        return Response(serializer.data)


class ExportIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        GET /api/export/ingested/?batch=<batch_id>
        - Si batch dado: devuelve sólo los valores con upload_batch=batch_id
        - Si no: devuelve todos los BLOQUEADO (comportamiento antiguo)
        """
        batch = request.GET.get('batch')
        if batch:
            qs = IocEntry.objects.filter(upload_batch=batch).order_by('ioc_type__name', 'value')
        else:
            qs = IocEntry.objects.filter(status__iexact='BLOQUEADO').order_by('ioc_type__name', 'value')
        lines = [smart_str(i.value) for i in qs]
        content = "\n".join(lines) + ("\n" if lines else "")
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="iocs_ingestados.txt"'
        return response


    def post(self, request):
        items = request.data.get('items', [])
        if not isinstance(items, (list, tuple)):
            return Response({'detail': 'items debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)

        items_clean = [str(i).strip() for i in items if not is_invalid_value(i)]
        if not items_clean:
            return Response({'detail': 'No hay items válidos para exportar'}, status=status.HTTP_400_BAD_REQUEST)

        existing = list(IocEntry.objects.filter(value__in=items_clean).values_list('value', flat=True))
        content = "\n".join([smart_str(v) for v in existing]) + ("\n" if existing else "")
        resp = HttpResponse(content, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="iocs_ingestados.txt"'
        return resp


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


# Audit and Purge API
class AuditCreateSerializer:
    # lightweight inline serializer replacement (we used drf_serializers earlier; keep simple)
    pass


# Re-use DRF serializer class for audit as in your code if available:
from rest_framework import serializers as drf_serializers


class AuditCreateSerializer(drf_serializers.Serializer):
    label = drf_serializers.CharField(max_length=200)


class AuditCreateView(APIView):
    permission_classes = [IsAdminUser]

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
    permission_classes = [IsAdminUser]

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


class BulkChangeStateView(APIView):
    """
    Cambia estado de IoCs recibidos por archivo o JSON lines.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, format=None):
        user = request.user.username if request.user.is_authenticated else 'system'

        # Obtener new_state
        new_state = None
        if 'new_state' in request.data:
            new_state = request.data.get('new_state')
        if new_state not in ('BLOQUEADO', 'DEPURADO'):
            return Response({'detail': 'Estado inválido. Use "BLOQUEADO" o "DEPURADO".'}, status=status.HTTP_400_BAD_REQUEST)

        # Obtener líneas desde archivo o JSON
        lines = []
        if 'file' in request.FILES:
            f = request.FILES['file']
            try:
                txt = f.read().decode('utf-8', errors='ignore')
            except Exception:
                f.seek(0)
                txt = b''.join(chunk for chunk in f.chunks()).decode('utf-8', errors='ignore')
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
        else:
            data_lines = request.data.get('lines')
            if isinstance(data_lines, list):
                lines = [str(l).strip() for l in data_lines if str(l).strip()]
            else:
                return Response({'detail': 'No se proporcionaron líneas o archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        if not lines:
            return Response({'detail': 'Lista de IoCs vacía.'}, status=status.HTTP_400_BAD_REQUEST)

        updated = []
        not_found = []
        errors = []

        with transaction.atomic():
            for val in lines:
                if is_invalid_value(val):
                    errors.append({'value': val, 'error': 'invalid/placeholder'})
                    continue
                try:
                    try:
                        ioc = IocEntry.objects.get(value=val)
                    except IocEntry.DoesNotExist:
                        not_found.append(val)
                        continue

                    old = ioc.status
                    if old == new_state:
                        updated.append({'value': val, 'unchanged': True, 'old': old})
                        continue

                    ioc.status = new_state
                    ioc.save(update_fields=['status'])
                    try:
                        IocHistory.objects.create(ioc=ioc, action=f'STATE_CHANGE {old} -> {new_state}', user=user, comment=f'Bulk update via UI by {user}')
                    except Exception:
                        pass
                    updated.append({'value': val, 'old': old, 'new': new_state})
                except Exception as e:
                    errors.append({'value': val, 'error': str(e)})

        return Response({
            'updated_count': len([u for u in updated if not u.get('unchanged')]),
            'updated': updated,
            'not_found': not_found,
            'errors': errors
        }, status=status.HTTP_200_OK)
        


# reemplaza o actualiza tu GenerarReporteView con esto (usa importaciones que ya tienes)
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Count

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



