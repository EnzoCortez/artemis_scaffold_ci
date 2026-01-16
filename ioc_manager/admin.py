from django.contrib import admin
from .models import IocType, Tool,ToolHashType, IocEntry, IocTool
admin.site.register(IocType)
admin.site.register(Tool)
admin.site.register(ToolHashType)
# Firewall removed
# FirewallIocType removed
admin.site.register(IocEntry)
admin.site.register(IocTool)
# IocHistory removed
