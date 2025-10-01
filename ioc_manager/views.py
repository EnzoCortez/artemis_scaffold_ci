import io
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import render
from .models import IocEntry, IocType, IocTool, IocHistory
from .serializers import IocEntrySerializer
from rest_framework.permissions import IsAdminUser
from rest_framework import serializers as drf_serializers
permission_classes = [permissions.AllowAny]

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
        text = file_obj.read().decode('utf-8', errors='ignore')
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        duplicates = []
        new = []
        for line in lines:
            ioc_type = None
            if '@' in line:
                ioc_type = IocType.objects.filter(name__iexact='Correo').first()
            elif all(ch.isdigit() or ch=='.' for ch in line):
                ioc_type = IocType.objects.filter(name__iexact='IP').first()
            else:
                ioc_type = IocType.objects.filter(name__iexact='Dominio').first()
            if not ioc_type:
                continue
            exists = IocEntry.objects.filter(ioc_type=ioc_type, value=line).exists()
            if exists:
                duplicates.append(line)
            else:
                new.append(line)
        return Response({'duplicates': duplicates, 'new': new})
    
class LoadNewIocsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, format=None):
        data = request.data
        items = data.get('items', [])
        user = request.user.username if request.user.is_authenticated else 'system'
        inserted = []
        errors = []
        for item in items:
            value = item.get('value')
            type_name = item.get('type')
            ioc_type = IocType.objects.filter(name__iexact=type_name).first()
            if not ioc_type:
                errors.append({'value': value, 'error': 'Tipo desconocido'})
                continue
            try:
                obj, created = IocEntry.objects.get_or_create(ioc_type=ioc_type, value=value, defaults={'created_by': request.user if request.user.is_authenticated else None})
                if created:
                    inserted.append(value)
                    IocHistory.objects.create(ioc=obj, action='INGESTADO', user=user)
            except Exception as e:
                errors.append({'value': value, 'error': str(e)})
        return Response({'inserted': inserted, 'errors': errors})
    
class IocListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        qs = IocEntry.objects.all().order_by('-created_at')
        serializer = IocEntrySerializer(qs, many=True)
        return Response(serializer.data)
class ExportIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        qs = IocEntry.objects.filter(status='BLOQUEADO').order_by('ioc_type__name', 'value')
        lines = [f"{i.value}" for i in qs]
        content = "\n".join(lines)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="iocs_ingestados.txt"'
        return response
class ExportNotIngestedTxtView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        items = request.data.get('items', [])
        not_ingested = []
        for v in items:
            exists = IocEntry.objects.filter(value=v).exists()
            if not exists:
                not_ingested.append(v)
        content = "\n".join(not_ingested)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="iocs_no_ingestados.txt"'
        return response
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
        ioc.save()
        IocHistory.objects.create(ioc=ioc, action=f'STATE_CHANGE {old} -> {new_state}', user=user)
        return Response({'detail': 'Estado actualizado'})
# Audit and Purge API
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
        qs = IocEntry.objects.filter(status='DEPURADO')
        count = qs.count()
        if dry_run:
            return Response({'dry_run': True, 'to_delete': count})
        for ioc in qs.iterator():
            IocHistory.objects.create(ioc=ioc, action=f'PURGED AFTER AUDIT {audit_id}', user=request.user.username, comment=f'Purgado vía UI tras auditoría {audit_id} por {request.user.username}')
        qs.delete()
        return Response({'detail': f'Purgados {count} IoCs', 'purged_count': count})
    
    from rest_framework.permissions import IsAuthenticated
from django.db import transaction

class BulkChangeStateView(APIView):

    def post(self, request, format=None):
        """
        Cambia el estado de todos los IoCs que coincidan con las líneas proporcionadas.
        Se puede enviar:
         - multipart/form-data con 'file' (archivo txt) y 'new_state'
         - application/json con {'lines': [...], 'new_state': 'BLOQUEADO'|'DEPURADO'}
        Respuesta:
         {'updated_count': n, 'updated': [...], 'not_found': [...], 'errors': [...]}
        """
        user = request.user.username if request.user.is_authenticated else 'system'

        # Obtener new_state
        new_state = None
        # si es form-data
        if 'new_state' in request.data:
            new_state = request.data.get('new_state')
        # validar
        if new_state not in ('BLOQUEADO', 'DEPURADO'):
            return Response({'detail': 'Estado inválido. Use "BLOQUEADO" o "DEPURADO".'}, status=status.HTTP_400_BAD_REQUEST)

        # Obtener líneas desde archivo o JSON
        lines = []
        # 1) archivo en request.FILES
        if 'file' in request.FILES:
            f = request.FILES['file']
            try:
                txt = f.read().decode('utf-8', errors='ignore')
            except Exception:
                # si es UploadedFile con .chunks()
                f.seek(0)
                txt = b''.join(chunk for chunk in f.chunks()).decode('utf-8', errors='ignore')
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
        else:
            # 2) JSON body con lines
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
        # Realizar cambios en una transacción para consistencia
        with transaction.atomic():
            for val in lines:
                try:
                    # Buscar (case-insensitive?) aquí usamos exact match por value
                    try:
                        ioc = IocEntry.objects.get(value=val)
                    except IocEntry.DoesNotExist:
                        not_found.append(val)
                        continue

                    old = ioc.status
                    if old == new_state:
                        # ya tiene ese estado; lo omitimos o lo contamos como no necesario
                        updated.append({'value': val, 'unchanged': True, 'old': old})
                        continue

                    ioc.status = new_state
                    ioc.save(update_fields=['status'])
                    IocHistory.objects.create(ioc=ioc, action=f'STATE_CHANGE {old} -> {new_state}', user=user, comment=f'Bulk update via UI by {user}')
                    updated.append({'value': val, 'old': old, 'new': new_state})
                except Exception as e:
                    errors.append({'value': val, 'error': str(e)})

        return Response({
            'updated_count': len([u for u in updated if not u.get('unchanged')]),
            'updated': updated,
            'not_found': not_found,
            'errors': errors
        }, status=status.HTTP_200_OK)
        
        

