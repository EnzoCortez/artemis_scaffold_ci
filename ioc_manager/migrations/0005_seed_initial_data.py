from django.db import migrations

def seed_data(apps, schema_editor):
    IocType = apps.get_model('ioc_manager', 'IocType')
    Tool = apps.get_model('ioc_manager', 'Tool')
    ToolIndicatorRule = apps.get_model('ioc_manager', 'ToolIndicatorRule')

    # 1. Ensure IocTypes exist
    # Based on utils.py detect_ioc_type
    ioc_types_names = ["IP", "Hash", "Dominio", "URL", "Correo"]
    ioc_type_map = {}
    for name in ioc_types_names:
        obj, _ = IocType.objects.get_or_create(name=name)
        ioc_type_map[name] = obj

    # 2. Define Tools and their allowed types
    # Copied from ioc_manager/utils.py _VALID_TOOL_IOCTYPES to ensure stability
    TOOL_CONFIG = {
        "EDR (Crowdstrike)": {"IP", "Hash", "Dominio"}, # Canonical name in utils is "EDR (CROWDSTRIKE)", allowing mixed case for display
        "IPS": {"IP", "Hash"},
        "Firewall": {"IP"},
        "FTD": {"IP"},
        "Meraki": {"IP"},
        "Proxy": {"IP", "Dominio", "URL"},
        "Proofpoint": {"Correo", "Dominio", "IP"},
    }

    # 3. Create Tools and Rules
    for tool_name, allowed_types in TOOL_CONFIG.items():
        # Create Tool
        tool, _ = Tool.objects.get_or_create(name=tool_name)
        
        # Create Rules
        for type_name in allowed_types:
            if type_name in ioc_type_map:
                ToolIndicatorRule.objects.get_or_create(
                    tool=tool,
                    ioc_type=ioc_type_map[type_name],
                    defaults={'can_ingest': True}
                )

class Migration(migrations.Migration):

    dependencies = [
        ('ioc_manager', '0004_remove_iocentry_ioc_manager_ioc_typ_ce3ebf_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_data),
    ]
