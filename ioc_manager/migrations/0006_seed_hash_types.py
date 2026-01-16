from django.db import migrations

def seed_hash_types(apps, schema_editor):
    IocType = apps.get_model('ioc_manager', 'IocType')
    Tool = apps.get_model('ioc_manager', 'Tool')
    ToolHashType = apps.get_model('ioc_manager', 'ToolHashType')

    try:
        hash_type = IocType.objects.get(name="Hash")
    except IocType.DoesNotExist:
        print("IocType 'Hash' not found, skipping hash seed.")
        return

    # Configuration from utils.py
    HASH_CONFIG = {
        "EDR (Crowdstrike)": ["md5", "sha256"],
        "IPS": ["md5", "sha1", "sha256"],
    }

    for tool_name, algos in HASH_CONFIG.items():
        try:
            tool = Tool.objects.get(name__iexact=tool_name)
        except Tool.DoesNotExist:
            print(f"Tool {tool_name} not found, skipping hash seed.")
            continue

        for algo in algos:
            ToolHashType.objects.get_or_create(
                tool=tool,
                ioc_type=hash_type,
                algorithm=algo
            )

def reverse_seed(apps, schema_editor):
    # Optional: Logic to remove seeded hash types if needed
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('ioc_manager', '0005_seed_initial_data'),
    ]

    operations = [
        migrations.RunPython(seed_hash_types, reverse_seed),
    ]
