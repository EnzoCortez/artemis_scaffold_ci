import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.views import is_invalid_value, detect_ioc_type, validate_tool_accepts_ioc
from ioc_manager.models import Tool

lines = open('test_iocs.txt', 'r', encoding='utf-8').readlines()
lines = [l.strip() for l in lines if l.strip()]

skipped = []
clean_values = []
for line in lines:
    if is_invalid_value(line):
        skipped.append({'line': line, 'reason': 'invalid/placeholder'})
    else:
        clean_values.append(line)

all_tool_names = list(Tool.objects.values_list('name', flat=True))

new_items = []
for value in clean_values:
    try:
        detected = detect_ioc_type(value)
    except Exception:
        detected = ''

    if not detected:
        skipped.append({'line': value, 'reason': 'No pudo detectar tipo (formato no soportado)'})
        continue

    supported_by_any = False
    for t_name in all_tool_names:
        is_valid, _ = validate_tool_accepts_ioc(t_name, value)
        if is_valid:
            supported_by_any = True
            break
            
    if not supported_by_any:
        skipped.append({'line': value, 'reason': f'No soportado por ninguna herramienta ({detected})'})
        continue
    
    new_items.append({'value': value, 'detected_type': detected})

import json
print("SKIPPED:", json.dumps(skipped, indent=2))
print("NEW:", json.dumps(new_items, indent=2))
