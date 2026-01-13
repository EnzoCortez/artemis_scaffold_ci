import os
import sys
import django

sys.path.append("c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.models import IocEntry, IocTool
from ioc_manager.utils import associate_iocs_with_allowed_tools_bulk
from django.db.models import Count

def fix_relations():
    print("=== Fixing Missing IocTool Relations ===")
    
    # Identify IOCs with no tools
    # Option 1: Filter where tools is null
    missing_tools_qs = IocEntry.objects.filter(tools__isnull=True)
    count = missing_tools_qs.count()
    
    print(f"Found {count} IOCs without tool associations.")
    
    if count == 0:
        print("Nothing to fix.")
        return

    # Process in chunks to avoid memory issues
    BATCH_SIZE = 1000
    total_processed = 0
    
    # We need to fetch IDs first because iterating over a queryset while modifying it (adding relations) 
    # might affect results interpretation (though filter(tools__isnull=True) should be safe if we act on them).
    # Safest is to list IDs.
    
    ioc_ids = list(missing_tools_qs.values_list('id', flat=True))
    
    for i in range(0, len(ioc_ids), BATCH_SIZE):
        batch_ids = ioc_ids[i:i+BATCH_SIZE]
        iocs = IocEntry.objects.filter(id__in=batch_ids)
        
        print(f"Processing batch {i} to {i+len(batch_ids)}...")
        associate_iocs_with_allowed_tools_bulk(iocs)
        total_processed += len(batch_ids)
        
    print(f"\nDone. Processed {total_processed} IOCs.")
    
    # Verify
    still_missing = IocEntry.objects.filter(tools__isnull=True).count()
    print(f"Remaining orphaned IOCs: {still_missing}")

if __name__ == "__main__":
    fix_relations()
