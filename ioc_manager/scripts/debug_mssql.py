import os
import sys
import django

# Setup Django environment
sys.path.append("c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.models import IocEntry, Tool, ToolIndicatorRule, IocTool, Ingestion

def check_db_state():
    print("=== Database State Debug ===")
    
    # Check Tools
    tools = Tool.objects.all()
    print(f"Total Tools: {tools.count()}")
    for t in tools:
        print(f" - {t.name} (ID: {t.id})")

    # Check Rules
    rules = ToolIndicatorRule.objects.all()
    print(f"\nTotal Rules: {rules.count()}")
    for r in rules:
        print(f" - {r.tool.name} accepts {r.ioc_type.name} (Ingest: {r.can_ingest})")

    # Check IOCs
    iocs_count = IocEntry.objects.count()
    print(f"\nTotal IocEntries: {iocs_count}")
    
    if iocs_count > 0:
        sample_ioc = IocEntry.objects.first()
        print(f"Sample IOC: {sample_ioc.value} (Type: {sample_ioc.ioc_type})")
        
        # Check relations for sample
        rels = IocTool.objects.filter(ioc=sample_ioc)
        print(f"IocTool relations for sample: {rels.count()}")
        
        ingestions = Ingestion.objects.filter(ioc=sample_ioc)
        print(f"Ingestions for sample: {ingestions.count()}")

    # Check orphaned IOCs (no tool relations)
    orphaned = IocEntry.objects.filter(tools__isnull=True).count()
    print(f"\nIOCs without Tool relations: {orphaned} / {iocs_count}")

if __name__ == "__main__":
    try:
        check_db_state()
    except Exception as e:
        print(f"Error connecting or querying DB: {e}")
