from django.core.management.base import BaseCommand
from ioc_manager.models import IocType, Tool, ToolIndicatorRule, ToolHashType
# Import definitions from utils to source of truth
from ioc_manager.utils import _VALID_TOOL_IOCTYPES

class Command(BaseCommand):
    help = 'Seeds initial data for Tools and IOC Types'

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...")

        # 1. Ensure IOC Types
        all_types = ["IP", "URL", "Dominio", "Hash", "Correo"]
        type_objs = {}
        for name in all_types:
            obj, created = IocType.objects.get_or_create(name=name)
            type_objs[name] = obj
            if created:
                self.stdout.write(f"Created IocType: {name}")

        # 2. Iterate Config
        for tool_name, config in _VALID_TOOL_IOCTYPES.items():
            # Create Tool
            tool, created = Tool.objects.get_or_create(name=tool_name)
            if created:
                self.stdout.write(f"Created Tool: {tool_name}")

            # allowed types
            allowed_types = config.get("types", set())
            for t_name in allowed_types:
                if t_name not in type_objs:
                    self.stdout.write(self.style.WARNING(f"Unknown IocType {t_name} in config for {tool_name}"))
                    continue
                
                # Rule
                rule, r_created = ToolIndicatorRule.objects.get_or_create(
                    tool=tool,
                    ioc_type=type_objs[t_name],
                    defaults={'can_ingest': True}
                )
                if r_created:
                     self.stdout.write(f"  + Rule: {tool_name} -> {t_name}")

                # Hash Algos
                if t_name == "Hash":
                    algos = config.get("hash_algos", set())
                    for algo in algos:
                        th, th_created = ToolHashType.objects.get_or_create(
                            tool=tool,
                            ioc_type=type_objs["Hash"],
                            algorithm=algo
                        )
                        if th_created:
                             self.stdout.write(f"  + HashType: {tool_name} -> {algo}")

        self.stdout.write(self.style.SUCCESS("Data seeding completed."))
