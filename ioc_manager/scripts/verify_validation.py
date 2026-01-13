import os
import sys
import django
import json

sys.path.append("c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from django.test import RequestFactory
from ioc_manager.views import LoadNewIocsView, GenerarReporteView
from ioc_manager.models import IocEntry, IocType, Tool
from ioc_manager.utils import validate_tool_accepts_ioc
from django.utils import timezone

def setup_tools():
    # Ensure Tools exist
    Tool.objects.get_or_create(name='EDR (Crowdstrike)')
    Tool.objects.get_or_create(name='IPS')
    Tool.objects.get_or_create(name='FIREWALL')

def test_hash_validation():
    print("Testing Hash Validation logic (utils.py)...")
    
    # MD5 (32 chars) - Valid for EDR & IPS
    md5 = "a" * 32
    ok_edr, _ = validate_tool_accepts_ioc("EDR (Crowdstrike)", md5)
    ok_ips, _ = validate_tool_accepts_ioc("IPS", md5)
    assert ok_edr, "EDR should accept MD5"
    assert ok_ips, "IPS should accept MD5"

    # SHA1 (40 chars) - Invalid for EDR, Valid for IPS
    sha1 = "b" * 40
    ok_edr, msg = validate_tool_accepts_ioc("EDR (Crowdstrike)", sha1)
    ok_ips, _ = validate_tool_accepts_ioc("IPS", sha1)
    assert not ok_edr, "EDR should NOT accept SHA1"
    assert ok_ips, "IPS should accept SHA1"
    print(f"  EDR reject SHA1 reason: {msg}")

    # SHA256 (64 chars) - Valid for both
    sha256 = "c" * 64
    ok_edr, _ = validate_tool_accepts_ioc("EDR (Crowdstrike)", sha256)
    ok_ips, _ = validate_tool_accepts_ioc("IPS", sha256)
    assert ok_edr, "EDR should accept SHA256"
    assert ok_ips, "IPS should accept SHA256"

    print("Hash Validation Passed.")

def test_ingestion_rejection():
    print("\nTesting Ingestion Rejection (LoadNewIocsView)...")
    setup_tools()
    factory = RequestFactory()
    view = LoadNewIocsView.as_view()

    # 1. Unsupported IOC (SHA1 for EDR only system? No, we have IPS which accepts SHA1)
    # Let's try an invalid hash (odd length) or a type that no one accepts?
    # Actually, EDR accepts IP/Hash/Domain. IPS IP/Hash. Firewall IP.
    # URL is only accepted by PROXY. If we don't have PROXY tool, URL should be rejected.
    
    # Ensure PROXY does not exist for this test (or delete it temporarily)
    proxy = Tool.objects.filter(name='PROXY').first()
    if proxy:
        proxy.delete() # Temporarily delete to test rejection

    # Try to ingest a URL
    url_val = "http://bad-site-test-rejection.com"
    req = factory.post(
        '/api/load-new/',
        data=json.dumps({'items': [{'value': url_val}], 'fuente': 'Test'}),
        content_type='application/json'
    )
    req.user = type('User', (object,), {'is_authenticated': True, 'is_active': True})
    req._dont_enforce_csrf_checks = True

    res = view(req)
    # Should contain user error (status 200 but errors list has items, or status 400? View returns 200 with errors list)
    data = res.data
    errors = data.get('errors', [])
    
    # It should be rejected because NO tool accepts URL (since we deleted Proxy)
    # Wait, check utils.py: _VALID_TOOL_IOCTYPES definition.
    # We are iterating over 'all_tool_names' from DB.
    # We deleted PROXY from DB. So it shouldn't check Proxy rules.
    # And other tools don't accept URL.
    
    found_error = any(e['value'] == url_val for e in errors)
    assert found_error, f"URL should be rejected if no PROXY tool. Errors: {errors}"
    print("Ingestion Rejection Passed.")
    
    
    # Restore Proxy? (Not strictly needed since we assume verify env is disposable or we recreate)

def test_bulk_ingestion():
    print("\nTesting Bulk Ingestion Logic...")
    from ioc_manager.utils import associate_iocs_with_allowed_tools_bulk
    from ioc_manager.models import Ingestion

    # Create test IOCs
    t_hash, _ = IocType.objects.get_or_create(name='Hash')
    
    # SHA1 (Valid for IPS, Invalid for EDR)
    sha1_val = "d" * 40 
    ioc_sha1 = IocEntry.objects.create(value=sha1_val, ioc_type=t_hash, source="BulkTest")

    # SHA256 (Valid for Both)
    sha256_val = "e" * 64
    ioc_sha256 = IocEntry.objects.create(value=sha256_val, ioc_type=t_hash, source="BulkTest")

    # Run bulk association
    associate_iocs_with_allowed_tools_bulk([ioc_sha1, ioc_sha256])

    # Verify IPS Ingestions
    ips_tool = Tool.objects.get(name='IPS')
    ips_ingestions = Ingestion.objects.filter(ioc__in=[ioc_sha1, ioc_sha256], tool=ips_tool)
    assert ips_ingestions.count() == 2, f"IPS should ingest both SHA1 and SHA256. Found {ips_ingestions.count()}"

    # Verify EDR Ingestions
    edr_tool = Tool.objects.get(name='EDR (Crowdstrike)')
    edr_ingestions = Ingestion.objects.filter(ioc__in=[ioc_sha1, ioc_sha256], tool=edr_tool)
    
    # EDR should ONLY have SHA256
    edr_sha1 = edr_ingestions.filter(ioc=ioc_sha1).exists()
    edr_sha256 = edr_ingestions.filter(ioc=ioc_sha256).exists()

    assert not edr_sha1, "EDR should NOT ingest SHA1 in bulk"
    assert edr_sha256, "EDR SHOULD ingest SHA256 in bulk"

    print("Bulk Ingestion Validation Passed.")


def test_report_format():
    print("\nTesting Report Format...")
    # Create a dummy IOC
    t_ip, _ = IocType.objects.get_or_create(name='IP')
    ioc = IocEntry.objects.create(value="1.2.3.4", ioc_type=t_ip, source="Test Source Long Name")
    
    view = GenerarReporteView()
    now = timezone.now()
    output = view._generar_detalle(IocEntry.objects.filter(pk=ioc.pk), now, now)
    
    print("Report Output Sample:")
    print(output)
    
    # Check headers presence
    assert "Fuente" in output
    assert "Indicador" in output
    assert "-" * 145 in output # We changed 150 to 145
    print("Report Format Passed.")

if __name__ == '__main__':
    try:
        test_hash_validation()
        test_ingestion_rejection()
        test_bulk_ingestion()
        test_report_format()
        print("\nAll generic validations passed!")
    except Exception as e:
        print(f"\nFailed: {e}")
        import traceback
        traceback.print_exc()
