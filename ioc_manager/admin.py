from django.contrib import admin
from .models import IocType, Tool,ToolHashType, IocEntry, IocTool, ToolIndicatorRule

class ToolIndicatorRuleInline(admin.TabularInline):
    model = ToolIndicatorRule
    extra = 1

class ToolAdmin(admin.ModelAdmin):
    inlines = [ToolIndicatorRuleInline]

admin.site.register(IocType)
admin.site.register(Tool, ToolAdmin)
admin.site.register(ToolHashType)
admin.site.register(IocEntry)
admin.site.register(IocTool)
