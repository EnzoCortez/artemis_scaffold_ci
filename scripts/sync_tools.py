import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.models import IocEntry
from ioc_manager.utils import associate_iocs_with_allowed_tools_bulk
from django.contrib.auth.models import User

user = User.objects.first()
iocs = list(IocEntry.objects.all())

print(f"Re-evaluating {len(iocs)} IoCs...")
associate_iocs_with_allowed_tools_bulk(iocs, user=user)
print("Done!")
