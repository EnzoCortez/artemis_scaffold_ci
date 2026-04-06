import uuid
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import IocEntry, IocType, IocTool, Tool
from .utils import detect_ioc_type, validate_tool_accepts_ioc
from .views import is_invalid_value

logger = logging.getLogger(__name__)

class ValidateToolInitialLoadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, format=None):
        file_obj = request.FILES.get('file')
        tool_id = request.data.get('tool_id')
        
        if not file_obj or not tool_id:
            return Response({'detail': 'Falta el archivo o tool_id.'}, status=400)
            
        try:
            tool = Tool.objects.get(pk=tool_id)
        except Tool.DoesNotExist:
            return Response({'detail': 'Herramienta no encontrada.'}, status=404)

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

        for line in lines:
            total += 1
            if is_invalid_value(line):
                skipped.append({'line': line, 'reason': 'Valor inválido o placeholder'})
            else:
                clean_values.append(line)

        clean_values = list(set(clean_values))

        # Check existing Iocs
        existing_qs = IocEntry.objects.filter(value__in=clean_values).select_related('ioc_type')
        existing_map = {ioc.value: ioc for ioc in existing_qs}

        # Check existing IocTool mapping for THIS tool
        ioc_ids = [ioc.id for ioc in existing_qs]
        existing_tool_qs = IocTool.objects.filter(ioc_id__in=ioc_ids, tool=tool).values_list('ioc_id', flat=True)
        already_linked_ioc_ids = set(existing_tool_qs)

        new_for_tool = []      # Exists in DB, but not linked to this tool
        brand_new_items = []   # Does not exist in DB at all
        already_linked = []    # Already in DB AND linked to this tool

        for value in clean_values:
            try:
                detected = detect_ioc_type(value)
            except Exception:
                detected = ''

            if not detected:
                skipped.append({'line': value, 'reason': 'No pudo detectar tipo'})
                continue
            
            # Validate specifically against THIS tool
            is_valid, reason = validate_tool_accepts_ioc(tool.name, value)
            if not is_valid:
                skipped.append({'line': value, 'reason': f'Rechazado por reglas: {reason}'})
                continue

            if value in existing_map:
                ioc = existing_map[value]
                if ioc.id in already_linked_ioc_ids:
                    already_linked.append(value)
                else:
                    new_for_tool.append({
                        'value': value,
                        'detected_type': detected,
                        'ioc_id': ioc.id
                    })
            else:
                brand_new_items.append({
                    'value': value,
                    'detected_type': detected
                })

        return Response({
            'brand_new': brand_new_items,
            'new_for_tool': new_for_tool,
            'already_linked': already_linked,
            'skipped': skipped,
            'summary': {
                'total_lines_processed': total,
                'unique_valid': len(clean_values),
                'brand_new': len(brand_new_items),
                'new_for_tool': len(new_for_tool),
                'already_linked': len(already_linked),
                'skipped': len(skipped)
            }
        }, status=status.HTTP_200_OK)


class ExecuteToolInitialLoadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, format=None):
        brand_new_items = request.data.get('brand_new', [])
        new_for_tool_items = request.data.get('new_for_tool', [])
        tool_id = request.data.get('tool_id')
        
        if not tool_id:
            return Response({'detail': 'Falta el ID de herramienta.'}, status=400)
            
        try:
            tool = Tool.objects.get(pk=tool_id)
        except Tool.DoesNotExist:
            return Response({'detail': 'Herramienta no encontrada.'}, status=404)

        if not isinstance(brand_new_items, list) or not isinstance(new_for_tool_items, list):
            return Response({'detail': 'Estructura de datos inválida.'}, status=400)
            
        source_name = f"{tool.name}"

        ioc_type_map = {t.name.lower(): t for t in IocType.objects.all()}

        created_iocs_count = 0
        linked_iocs_count = 0

        with transaction.atomic():
            # 1. Objeto IocEntry para los brand new
            new_ioc_entries = []
            brand_new_values = set()
            for item in brand_new_items:
                val = item.get('value')
                typ = item.get('detected_type', '').lower()
                if not val or not typ:
                    continue
                if typ in ioc_type_map and val not in brand_new_values:
                    brand_new_values.add(val)
                    new_ioc_entries.append(
                        IocEntry(
                            value=val,
                            ioc_type=ioc_type_map[typ],
                            source=source_name,
                            created_by=request.user
                        )
                    )
            
            if new_ioc_entries:
                IocEntry.objects.bulk_create(new_ioc_entries)
                created_iocs_count = len(new_ioc_entries)
            
            newly_created_qs = IocEntry.objects.filter(value__in=brand_new_values).values_list('id', flat=True)
            
            existing_values_to_link = [i.get('value') for i in new_for_tool_items if i.get('value')]
            existing_to_link_qs = IocEntry.objects.filter(value__in=existing_values_to_link).values_list('id', flat=True)

            all_ids_to_link = set(newly_created_qs) | set(existing_to_link_qs)

            already_linked_db = set(IocTool.objects.filter(ioc_id__in=all_ids_to_link, tool=tool).values_list('ioc_id', flat=True))
            
            ids_to_actually_link = all_ids_to_link - already_linked_db
            
            new_ioctool_links = [
                IocTool(
                    ioc_id=ioc_id,
                    tool=tool,
                    status='pending_ingest'
                )
                for ioc_id in ids_to_actually_link
            ]
            
            if new_ioctool_links:
                IocTool.objects.bulk_create(new_ioctool_links)
                linked_iocs_count = len(new_ioctool_links)

        return Response({
            'detail': 'Carga inicial completada.',
            'created_iocs': created_iocs_count,
            'linked_to_tool': linked_iocs_count
        }, status=status.HTTP_200_OK)
