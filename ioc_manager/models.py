
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class IocType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'artemis_db.ioc_type'
        verbose_name = "Tipo de IOC"
        verbose_name_plural = "Tipos de IOC"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    threshold = models.CharField(max_length=100, null=True, blank=True)
    vendor = models.CharField(max_length=100, null=True, blank=True) # Consolidated from Firewall

    class Meta:
        db_table = 'artemis_db.tool'
        verbose_name = "Herramienta"
        verbose_name_plural = "Herramientas"
        ordering = ("name",)

    def __str__(self):
        return self.name


class ToolIndicatorRule(models.Model):
    """
    Define qué tipos de IOC puede ingestar cada herramienta.
    (equivalente a tool_indicator_rule en el esquema legacy)
    """
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="indicator_rules")
    ioc_type = models.ForeignKey(IocType, on_delete=models.CASCADE, related_name="tool_rules")
    can_ingest = models.BooleanField(default=True)

    class Meta:
        db_table = 'artemis_db.tool_indicator_rule'
        unique_together = ("tool", "ioc_type")
        verbose_name = "Regla herramienta-indicador"
        verbose_name_plural = "Reglas herramienta-indicador"

    def __str__(self):
        return f"{self.tool} -> {self.ioc_type} ({'ingesta' if self.can_ingest else 'no'})"


class ToolHashType(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='hash_types')
    ioc_type = models.ForeignKey(IocType, on_delete=models.CASCADE)
    algorithm = models.CharField(max_length=20)

    class Meta:
        db_table = 'artemis_db.tool_hash_type'
        unique_together = ('tool', 'ioc_type', 'algorithm')
        verbose_name = "Algoritmo de hash por herramienta"

    def __str__(self):
        return f"{self.tool} - {self.algorithm}"





class IocEntry(models.Model):
    STATUS_BLOCKED = 'BLOQUEADO'
    STATUS_CLEARED = 'DEPURADO'
    STATUS_CHOICES = [
        (STATUS_BLOCKED, 'Bloqueado'),
        (STATUS_CLEARED, 'Depurado'),
    ]

    ioc_type = models.ForeignKey(IocType, on_delete=models.PROTECT, related_name='iocs')
    value = models.CharField(max_length=500)
    value_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)  # SHA256 para indexación eficiente
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BLOCKED)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Campos adicionales útiles
    source = models.CharField(max_length=100, null=True, blank=True)
    upload_batch = models.CharField(max_length=36, null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'artemis_db.ioc_entry'
        unique_together = ('ioc_type', 'value') # Mantener value por ahora, luego migrar a value_hash
        indexes = [
            models.Index(fields=['ioc_type', 'value_hash']), # Index optimizado
            models.Index(fields=['status']),
            models.Index(fields=['upload_batch']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.value} ({self.ioc_type})"

    # Helper: register ingestion to a tool
    # register_ingestion removed (deprecated)


class IocTool(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_INGESTED = 'ingested'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_INGESTED, 'Ingested'),
        (STATUS_ERROR, 'Error'),
    ]

    ioc = models.ForeignKey(IocEntry, on_delete=models.CASCADE, related_name='tools')
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='iocs')
    
    # Merged Ingestion fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    ingested_at = models.DateTimeField(null=True, blank=True)
    detail = models.TextField(null=True, blank=True)  # Error logs etc
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'artemis_db.ioc_tool'
        unique_together = ('ioc', 'tool')
        verbose_name = "Relación IOC - Herramienta"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['ingested_at'])
        ]




class IocLoadBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50)
    total = models.IntegerField(default=0)
    inserted = models.IntegerField(default=0)
    duplicated = models.IntegerField(default=0)

    class Meta:
        db_table = 'artemis_db.ioc_load_batch'

    def __str__(self):
        return f"Lote {self.id} - {self.source}"


class IocLoadResult(models.Model):
    STATUS_CHOICES = (
        ('INGESTADO', 'INGESTADO'),
        ('DUPLICADO', 'DUPLICADO'),
    )

    batch = models.ForeignKey(IocLoadBatch, on_delete=models.CASCADE, related_name='results')
    value = models.CharField(max_length=255)
    ioc_type = models.CharField(max_length=30)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'artemis_db.ioc_load_result'

    def __str__(self):
        return f"{self.value} ({self.status})"
 

