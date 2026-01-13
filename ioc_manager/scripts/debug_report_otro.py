import os
import sys
import django
from django.test import RequestFactory
from django.utils import timezone
from datetime import timedelta

sys.path.append("c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.views import GenerarReporteView
from ioc_manager.models import IocEntry, IocType

def test_report_otro():
    print("=== Testing Report Filter 'Otro' ===")
    
    # Setup Data
    t_ip, _ = IocType.objects.get_or_create(name='IP')
    now = timezone.now().date()
    
    # Clean previous test data
    IocEntry.objects.filter(source__in=["TestCustomSource", "IBM"]).delete()
    
    # Create IOC with standard source
    IocEntry.objects.create(value="1.1.1.1", ioc_type=t_ip, source="IBM")
    
    # Create IOC with custom source
    IocEntry.objects.create(value="2.2.2.2", ioc_type=t_ip, source="TestCustomSource")
    
    print("Created IOCs: 1.1.1.1 (IBM), 2.2.2.2 (TestCustomSource)")
    
    # Test Filter "Otro"
    view = GenerarReporteView()
    factory = RequestFactory()
    
    # Simulate GET /api/reporte/?inicio=...&fin=...&fuente=Otro
    req = factory.get(f'/api/reporte/?inicio={now}&fin={now}&fuente=Otro')
    req.user = type('User', (object,), {'is_authenticated': True})
    
    print("\nRequesting report with source='Otro'...")
    res = view.get(req)
    content = res.content.decode('utf-8')
    
    print("Report Content:")
    print("-" * 20)
    print(content)
    print("-" * 20)
    
    if "2.2.2.2" in content or "TestCustomSource" in content:
        print("SUCCESS: Found custom source in 'Otro' filter.")
    else:
        print("FAILURE: Custom source NOT found in 'Otro' filter.")

if __name__ == "__main__":
    test_report_otro()
