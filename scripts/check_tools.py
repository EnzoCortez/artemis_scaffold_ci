import os
import django
import sys

# Setup Django configs
sys.path.append('c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.models import Tool

print(f"Total Tools: {Tool.objects.count()}")
for t in Tool.objects.all():
    print(f"- {t.name}")
