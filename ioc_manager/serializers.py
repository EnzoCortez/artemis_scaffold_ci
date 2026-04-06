from rest_framework import serializers
from .models import IocEntry, IocType, Tool, IocTool
class IocTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IocType
        fields = '__all__'
class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = '__all__'
class IocEntrySerializer(serializers.ModelSerializer):
    ioc_type = IocTypeSerializer(read_only=True)
    ioc_type_id = serializers.PrimaryKeyRelatedField(queryset=IocType.objects.all(), source='ioc_type', write_only=True)
    tools = serializers.SerializerMethodField()

    class Meta:
        model = IocEntry
        fields = ['id', 'ioc_type', 'ioc_type_id', 'value', 'status', 'created_at', 'tools']
        
    def get_tools(self, obj):
        # obj.tools returns IocTool instances because related_name='tools'
        return [t.tool.name for t in obj.tools.all() if t.tool]
class IocToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = IocTool
        fields = '__all__'
