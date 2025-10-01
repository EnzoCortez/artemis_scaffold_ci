from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class IocType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self): return self.name
    
class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    threshold = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self): return self.name
    
class ToolHashType(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='hash_types')
    ioc_type = models.ForeignKey(IocType, on_delete=models.CASCADE)
    algorithm = models.CharField(max_length=20)
    class Meta:
        unique_together = ('tool', 'ioc_type', 'algorithm')
    def __str__(self): return f"{self.tool} - {self.algorithm}"
    
class Firewall(models.Model):
    name = models.CharField(max_length=100, unique=True)
    vendor = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self): return self.name
    
class FirewallIocType(models.Model):
    firewall = models.ForeignKey(Firewall, on_delete=models.CASCADE)
    ioc_type = models.ForeignKey(IocType, on_delete=models.CASCADE)
    class Meta:
        unique_together = ('firewall', 'ioc_type')
        
class IocEntry(models.Model):
    STATUS_CHOICES = [('BLOQUEADO','Bloqueado'),('DEPURADO','Depurado'),]
    ioc_type = models.ForeignKey(IocType, on_delete=models.PROTECT)
    value = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BLOQUEADO')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ('ioc_type', 'value')
        indexes = [models.Index(fields=['ioc_type', 'value']), models.Index(fields=['status'])]
    def __str__(self): return f"{self.value} ({self.ioc_type})"
    
class IocTool(models.Model):
    ioc = models.ForeignKey(IocEntry, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('ioc', 'tool')
        
class IocHistory(models.Model):
    ioc = models.ForeignKey(IocEntry, on_delete=models.CASCADE, related_name='history', null=True)
    action = models.CharField(max_length=100)
    user = models.CharField(max_length=150, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [models.Index(fields=['ioc', 'timestamp'])]
    def __str__(self): return f"{self.ioc} - {self.action} @ {self.timestamp}"




