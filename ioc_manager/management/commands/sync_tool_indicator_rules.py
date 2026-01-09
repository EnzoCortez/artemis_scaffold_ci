from django.core.management.base import BaseCommand
from ioc_manager.models import Tool, IocType, ToolIndicatorRule


VALID_RULES = {
    "EDR (CROWDSTRIKE)": {"IP", "Hash", "Dominio"},
    "IPS": {"IP", "Hash"},
    "FIREWALL": {"IP"},
    "FTD": {"IP"},
    "MERAKI": {"IP"},
    "PROXY": {"IP", "Dominio", "URL"},
    "PROOFPOINT": {"Correo", "Dominio", "IP"},
}


class Command(BaseCommand):
    help = "Sincroniza ToolIndicatorRule según reglas oficiales"

    def handle(self, *args, **options):
        self.stdout.write("🔧 Sincronizando ToolIndicatorRule...")

        for tool_name, allowed_types in VALID_RULES.items():
            try:
                tool = Tool.objects.get(name=tool_name)
            except Tool.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"⚠ Tool no existe: {tool_name}"))
                continue

            for ioc_type_name in allowed_types:
                try:
                    ioc_type = IocType.objects.get(name__iexact=ioc_type_name)
                except IocType.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ IocType '{ioc_type_name}' no existe (Tool={tool_name})"
                        )
                    )
                    continue

                rule, created = ToolIndicatorRule.objects.update_or_create(
                    tool=tool,
                    ioc_type=ioc_type,
                    defaults={"can_ingest": True},
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✔ Regla creada: {tool.name} -> {ioc_type.name}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS("✅ Sincronización finalizada"))
