import uuid
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import IocEntry, IocType, IocTool, Tool, ToolIndicatorRule, ToolHashType
from .utils import detect_ioc_type, detect_hash_algorithm
from .views import is_invalid_value

logger = logging.getLogger(__name__)

def get_in_chunks(qs, field_name, value_list, chunk_size=900):
    """
    Generador para dividir consultas grandes con __in= y evitar el límite de 2100 parámetros en MSSQL.
    Retorna los fragmentos de resultados QuerySet.
    """
    for i in range(0, len(value_list), chunk_size):
        chunk = value_list[i:i + chunk_size]
        yield qs.filter(**{f"{field_name}__in": chunk})


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

        from .utils import remove_defanging
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        lines = [remove_defanging(l) for l in raw_lines]

        total = 0
        skipped = []
        clean_values = []

        for line in lines:
            total += 1
            if is_invalid_value(line):
                skipped.append({'line': line, 'reason': 'Valor inválido o placeholder'})
            elif len(line) > 500:
                skipped.append({'line': line[:50] + '[...]', 'reason': 'Supera límite de 500 caracteres (No soportado por BD)'})
            else:
                clean_values.append(line)

        clean_values = list(set(clean_values))

        # Check existing Iocs in CHUNKS
        existing_map = {}
        for qs_chunk in get_in_chunks(IocEntry.objects.select_related('ioc_type'), 'value', clean_values):
            for ioc in qs_chunk:
                existing_map[ioc.value] = ioc

        # Check existing IocTool mapping for THIS tool in CHUNKS
        ioc_ids = [ioc.id for ioc in existing_map.values()]
        already_linked_ioc_ids = set()
        for qs_chunk in get_in_chunks(IocTool.objects.filter(tool=tool), 'ioc_id', ioc_ids):
            already_linked_ioc_ids.update(qs_chunk.values_list('ioc_id', flat=True))

        new_for_tool = []      
        brand_new_items = []   
        already_linked = []    

        # PRE-LOAD VALIDATION RULES O(1)
        allowed_types_qs = ToolIndicatorRule.objects.filter(tool=tool, can_ingest=True).select_related('ioc_type')
        allowed_types = {rule.ioc_type.name.lower() for rule in allowed_types_qs}
        
        allowed_hash_algos = set(ToolHashType.objects.filter(tool=tool, ioc_type__name__iexact="Hash").values_list('algorithm', flat=True))
        allowed_hash_algos = {h.lower().strip() for h in allowed_hash_algos}

        def fast_validate(tool_obj, val, detect_typ):
            typ_lower = detect_typ.lower()
            if typ_lower not in allowed_types:
                return False, f"'{tool_obj.name}' no tiene habilitada la ingesta de '{detect_typ}'."
            if typ_lower == "hash":
                algo = detect_hash_algorithm(val)
                if not algo:
                    return False, "Hash inválido."
                if allowed_hash_algos and algo.lower().strip() not in allowed_hash_algos:
                     return False, f"'{tool_obj.name}' solo acepta hashes: {', '.join(allowed_hash_algos)}."
            return True, None

        for value in clean_values:
            try:
                detected = detect_ioc_type(value)
            except Exception:
                detected = ''

            if not detected:
                skipped.append({'line': value, 'reason': 'No pudo detectar tipo'})
                continue
            
            # Fast Validation
            is_valid, reason = fast_validate(tool, value, detected)
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
            
        source_name = "Base Artemis"

        ioc_type_map = {t.name.lower(): t for t in IocType.objects.all()}

        created_iocs_count = 0
        linked_iocs_count = 0

        with transaction.atomic():
            # 1. Crear IocEntry para brand new (Chunk de creación masiva)
            new_ioc_entries = []
            requested_brand_new_values = set()
            for item in brand_new_items:
                val = item.get('value')
                if val:
                    requested_brand_new_values.add(val)
                    
            # --- DEFENSIVE CHECK: Case Insensitive for MSSQL ---
            unexpectedly_existing_values_lower = set()
            for qs_chunk in get_in_chunks(IocEntry.objects.all(), 'value', list(requested_brand_new_values)):
                for found_val in qs_chunk.values_list('value', flat=True):
                    unexpectedly_existing_values_lower.add(found_val.lower())
                
            added_values_lower = set()
            for item in brand_new_items:
                val = item.get('value')
                typ = item.get('detected_type', '').lower()
                if not val or not typ:
                    continue
                val_lower = val.lower()
                if typ in ioc_type_map and val_lower not in unexpectedly_existing_values_lower and val_lower not in added_values_lower:
                    added_values_lower.add(val_lower)
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
            
            # Obtener IDs de los recién creados con Chunking
            newly_created_qs = set()
            for qs_chunk in get_in_chunks(IocEntry.objects.all(), 'value', [x.value for x in new_ioc_entries]):
                newly_created_qs.update(qs_chunk.values_list('id', flat=True))
            
            # Obtener IDs de los que existen para asociar (Chunking)
            existing_values_to_link = [i.get('value') for i in new_for_tool_items if i.get('value')]
            existing_to_link_qs = set()
            for qs_chunk in get_in_chunks(IocEntry.objects.all(), 'value', existing_values_to_link):
                existing_to_link_qs.update(qs_chunk.values_list('id', flat=True))

            all_ids_to_link = newly_created_qs | existing_to_link_qs

            # Encontrar cuáles ya están enlazados (Chunking)
            already_linked_db = set()
            for qs_chunk in get_in_chunks(IocTool.objects.filter(tool=tool), 'ioc_id', list(all_ids_to_link)):
                already_linked_db.update(qs_chunk.values_list('ioc_id', flat=True))
            
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
