from django.contrib import admin
from .models import IocType, Tool, ToolHashType, IocEntry, IocTool, ToolIndicatorRule, IocLoadBatch

class ToolIndicatorRuleInline(admin.TabularInline):
    model = ToolIndicatorRule
    extra = 1

class ToolAdmin(admin.ModelAdmin):
    inlines = [ToolIndicatorRuleInline]

class IocEntryAdmin(admin.ModelAdmin):
    list_display = ('value', 'ioc_type', 'status', 'created_by', 'ingestion_attempts', 'created_at')
    list_filter = ('ioc_type', 'status', 'created_by')
    search_fields = ('value', 'upload_batch')

class IocLoadBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'file_name', 'uploaded_by', 'total', 'inserted', 'duplicated', 'rejected', 'created_at')
    list_filter = ('source', 'uploaded_by', 'created_at')
    search_fields = ('source', 'file_name', 'batch_uuid')
    readonly_fields = ('created_at',)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        
        if hasattr(response, 'context_data') and 'cl' in response.context_data:
            cl = response.context_data['cl']
            # Obtener queryset filtrado y limitado a las últimas 50 cargas para legibilidad
            filtered_qs = cl.queryset.order_by('-created_at')[:50]
            chart_data = list(reversed(filtered_qs))
            
            labels = []
            for b in chart_data:
                dt = b.created_at
                if dt:
                    # Formato legible de fecha y hora local
                    labels.append(dt.strftime("%d/%m %H:%M"))
                else:
                    labels.append(f"Lote {b.id}")

            data = {
                'labels': labels,
                'inserted': [b.inserted for b in chart_data],
                'duplicated': [b.duplicated for b in chart_data],
                'rejected': [b.rejected for b in chart_data],
            }
            
            import json
            from django.core.serializers.json import DjangoJSONEncoder
            response.context_data['chart_data_json'] = json.dumps(data, cls=DjangoJSONEncoder)
            
        return response

admin.site.register(IocType)
admin.site.register(Tool, ToolAdmin)
admin.site.register(ToolHashType)
admin.site.register(IocEntry, IocEntryAdmin)
admin.site.register(IocTool)
admin.site.register(IocLoadBatch, IocLoadBatchAdmin)
