from django.core.management.base import BaseCommand, CommandError
from ioc_manager.models import IocHistory, IocEntry
class Command(BaseCommand):
    help = 'Purgar IoCs con estado DEPURADO tras auditoría. Requiere --audit-history-id y --performed-by'
    def add_arguments(self, parser):
        parser.add_argument('--audit-history-id', type=int, required=True)
        parser.add_argument('--performed-by', type=str, required=True)
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        audit_id = options['audit_history_id']
        user = options['performed_by']
        dry = options['dry_run']
        try:
            audit = IocHistory.objects.get(id=audit_id)
        except IocHistory.DoesNotExist:
            raise CommandError('Auditoría no encontrada')
        if 'AUDIT' not in (audit.action or '').upper():
            raise CommandError('El historial proporcionado no es una auditoría válida')
        qs = IocEntry.objects.filter(status='DEPURADO')
        count = qs.count()
        if dry:
            self.stdout.write(self.style.WARNING(f"DRY RUN: {count} registros PROYECTADOS a purgar"))
            return
        for ioc in qs.iterator():
            IocHistory.objects.create(ioc=ioc, action=f'PURGED AFTER AUDIT {audit_id}', user=user, comment=f'Purgado via CLI tras auditoría {audit_id} por {user}')
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Purgados: {count}"))
