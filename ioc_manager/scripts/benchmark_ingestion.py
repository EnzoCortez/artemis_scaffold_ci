import os
import sys
import django
import time
import random
import string
from django.test import RequestFactory
import json

sys.path.append("c:\\Users\\lenovo\\OneDrive\\Desktop\\Artemis_Antigravity\\artemis_scaffold")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.views import LoadNewIocsView
from ioc_manager.models import IocEntry

def benchmark_ingestion():
    print("=== Benchmarking Ingestion Speed ===")
    
    COUNT = 1000
    print(f"Generating {COUNT} random IP IOCs...")
    
    items = []
    for i in range(COUNT):
        # random IP
        ip = ".".join(str(random.randint(1, 255)) for _ in range(4))
        items.append(ip)
        
    print(f"Sample: {items[:3]}")
    
    view = LoadNewIocsView.as_view()
    factory = RequestFactory()
    
    data = {
        "items": items,
        "fuente": "BenchmarkSource"
    }
    
    req = factory.post(
        '/api/load-new/',
        data=json.dumps(data),
        content_type='application/json'
    )
    req.user = type('User', (object,), {'is_authenticated': True, 'username': 'benchmarker'})
    
    print("\nStarting Ingestion...")
    start_time = time.time()
    
    res = view(req)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nResponse Code: {res.status_code}")
    print(f"Response Data: {res.data}")
    
    print(f"\nTime taken: {duration:.4f} seconds")
    print(f"Speed: {COUNT / duration:.2f} IOCs/sec")

    # Cleanup
    print("\nCleaning up...")
    IocEntry.objects.filter(source="BenchmarkSource").delete()

if __name__ == "__main__":
    benchmark_ingestion()
