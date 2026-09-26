import uuid
from django.db import models


class MaxUser(models.Model):
    max_user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"User {self.max_user_id} ({self.first_name})"


class Upload(models.Model):
    class Source(models.TextChoices):
        MINIAPP = "miniapp"
        DEMO = "demo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(MaxUser, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to="uploads/%Y/%m/", null=True, blank=True)
    filename = models.CharField(max_length=255)
    mime = models.CharField(max_length=127, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MINIAPP)
    columns = models.JSONField(default=list)
    sample_rows = models.JSONField(default=list)
    all_rows = models.JSONField(default=list)
    suggested_mapping = models.JSONField(default=dict)
    mapping = models.JSONField(null=True, blank=True)
    status_map = models.JSONField(null=True, blank=True)
    guest_session = models.CharField(max_length=128, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Snapshot(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing"
        READY = "ready"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(MaxUser, on_delete=models.CASCADE, null=True, blank=True)
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, null=True, blank=True)
    scan_no = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    guest_session = models.CharField(max_length=128, blank=True, default="", db_index=True)
    is_guest = models.BooleanField(default=False, db_index=True)
    filename = models.CharField(max_length=255, blank=True)
    archetype = models.CharField(max_length=32, default="deals")
    engine_version = models.CharField(max_length=32, default="1")
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    mapping = models.JSONField(default=dict)
    quality = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.READY)
    progress = models.PositiveSmallIntegerField(default=100)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Diagnosis data
    headline = models.TextField(blank=True)
    body = models.TextField(blank=True)
    findings = models.JSONField(default=list)
    coverage = models.JSONField(default=dict)
    totals = models.JSONField(default=dict)
    all_metrics = models.JSONField(default=dict)
    ok_list = models.JSONField(default=list)
    low_sample = models.JSONField(default=list)

    class Meta:
        ordering = ['-created_at']


class Deal(models.Model):
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="deals")
    deal_id = models.CharField(max_length=64)
    client = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    manager = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    list_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    discount_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status_raw = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(null=True, blank=True)
    first_contact_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["snapshot", "-amount"]),
            models.Index(fields=["snapshot", "status"]),
        ]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"

    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    tool_calls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
