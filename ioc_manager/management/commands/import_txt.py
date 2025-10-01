from django.core.management.base import BaseCommand
from ioc_manager.models import IocType, IocEntry, IocHistory
class Command(BaseCommand):
    help = 'Importar IoCs desde un archivo TXT (ruta en argumento)'
    def add_arguments(self, parser):
        parser.add_argument('filepath', type=str)
        parser.add_argument('--user', type=str, default='system')
    def handle(self, *args, **options):
        path = options['filepath']
        username = options['user']
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip()]
        inserted = 0
        for line in lines:
            if '@' in line:
                tname = 'Correo'
            elif line.replace('.', '').isdigit():
                tname = 'IP'
            else:
                tname = 'Dominio'
            ioc_type = IocType.objects.filter(name__iexact=tname).first()
            if not ioc_type:
                self.stdout.write(self.style.WARNING(f"Tipo no encontrado para {line} - omitiendo"))
                continue
            obj, created = IocEntry.objects.get_or_create(ioc_type=ioc_type, value=line)
            if created:
                IocHistory.objects.create(ioc=obj, action='INGESTADO', user=username)
                inserted += 1
        self.stdout.write(self.style.SUCCESS(f"Insertados: {inserted}"))
