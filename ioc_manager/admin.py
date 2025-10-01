from django.contrib import admin
from .models import IocType, Tool, ToolHashType, Firewall, FirewallIocType, IocEntry, IocTool, IocHistory
admin.site.register(IocType)
admin.site.register(Tool)
admin.site.register(ToolHashType)
admin.site.register(Firewall)
admin.site.register(FirewallIocType)
admin.site.register(IocEntry)
admin.site.register(IocTool)
admin.site.register(IocHistory)
