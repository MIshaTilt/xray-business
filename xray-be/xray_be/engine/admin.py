from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import MaxUser, Upload, Snapshot, Deal, ChatMessage, LLMUsageLog


class LLMUsageLogInLine(admin.TabularInline):
    model = LLMUsageLog
    extra = 0
    fields = ('operation', 'model', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'created_at')
    readonly_fields = ('operation', 'model', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'created_at')
    can_delete = False
    max_num = 20
    ordering = ('-created_at',)


@admin.register(MaxUser)
class MaxUserAdmin(admin.ModelAdmin):
    list_display = (
        'max_user_id',
        'first_name',
        'prompt_tokens_display',
        'completion_tokens_display',
        'total_tokens_display',
        'snapshots_count',
        'created_at'
    )
    search_fields = ('max_user_id', 'first_name')
    readonly_fields = ('max_user_id', 'created_at', 'prompt_tokens', 'completion_tokens', 'total_tokens')
    ordering = ('-total_tokens', '-created_at')
    inlines = [LLMUsageLogInLine]

    @admin.display(description='Входные (Prompt)', ordering='prompt_tokens')
    def prompt_tokens_display(self, obj):
        val = f"{obj.prompt_tokens:,}".replace(',', ' ')
        return format_html('<span style="color: #4b5563;">📥 {}</span>', val)

    @admin.display(description='Выходные (Completion)', ordering='completion_tokens')
    def completion_tokens_display(self, obj):
        val = f"{obj.completion_tokens:,}".replace(',', ' ')
        return format_html('<span style="color: #4b5563;">📤 {}</span>', val)

    @admin.display(description='Всего токенов', ordering='total_tokens')
    def total_tokens_display(self, obj):
        val = f"{obj.total_tokens:,}".replace(',', ' ')
        if obj.total_tokens > 0:
            return format_html('<b style="color: #2563eb; font-size: 13px;">⚡ {}</b>', val)
        return format_html('<span style="color: #999;">0</span>')

    @admin.display(description='Снимков')
    def snapshots_count(self, obj):
        return obj.snapshot_set.count()


@admin.register(LLMUsageLog)
class LLMUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user_display',
        'operation',
        'model',
        'prompt_tokens',
        'completion_tokens',
        'total_tokens',
        'created_at'
    )
    list_filter = ('operation', 'model', 'created_at')
    search_fields = ('user__max_user_id', 'user__first_name', 'operation', 'model')
    readonly_fields = (
        'id',
        'created_at',
        'user',
        'snapshot',
        'operation',
        'model',
        'prompt_tokens',
        'completion_tokens',
        'total_tokens',
        'duration_ms'
    )
    ordering = ('-created_at',)

    @admin.display(description='Пользователь')
    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:engine_maxuser_change', args=[obj.user.pk])
            return format_html('<a href="{}">👤 MAX: <b>{}</b> ({})</a>', url, obj.user.max_user_id, obj.user.first_name or '—')
        return format_html('<span style="color: #999;">Гость / Тест</span>')


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_display', 'filename', 'source', 'size_bytes', 'created_at')
    list_filter = ('source', 'created_at')
    search_fields = ('id', 'filename', 'guest_session', 'user__max_user_id', 'user__first_name')
    readonly_fields = ('id', 'created_at', 'owner_display')
    ordering = ('-created_at',)

    @admin.display(description='Владелец (User / Сессия)')
    def owner_display(self, obj):
        if obj.user:
            url = reverse('admin:engine_maxuser_change', args=[obj.user.pk])
            return format_html('<a href="{}">👤 MAX: <b>{}</b> ({})</a>', url, obj.user.max_user_id, obj.user.first_name or '—')
        if obj.guest_session:
            return format_html('<span style="color: #666;">🌐 Гость: {}</span>', obj.guest_session[:16] + ('...' if len(obj.guest_session) > 16 else ''))
        return format_html('<span style="color: #999;">—</span>')


class DealInline(admin.TabularInline):
    model = Deal
    extra = 0
    fields = ('deal_id', 'client', 'amount', 'status', 'manager', 'created_at')
    readonly_fields = ('deal_id', 'client', 'amount', 'status', 'manager', 'created_at')
    can_delete = False
    max_num = 20
    show_change_link = True


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ('role', 'content', 'created_at')
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False
    max_num = 30


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'scan_no',
        'owner_display',
        'headline',
        'status',
        'progress',
        'is_guest',
        'id',
        'created_at'
    )
    list_filter = ('status', 'is_guest', 'created_at')
    search_fields = (
        'id',
        'headline',
        'scan_no',
        'guest_session',
        'user__max_user_id',
        'user__first_name'
    )
    readonly_fields = ('id', 'created_at', 'owner_display')
    ordering = ('-created_at',)
    inlines = [ChatMessageInline, DealInline]

    @admin.display(description='Владелец (User ID / Гость)')
    def owner_display(self, obj):
        if obj.user:
            url = reverse('admin:engine_maxuser_change', args=[obj.user.pk])
            return format_html('<a href="{}">👤 MAX: <b>{}</b> ({})</a>', url, obj.user.max_user_id, obj.user.first_name or '—')
        if obj.guest_session:
            return format_html('<span style="color: #666;" title="{}">🌐 Гость: {}</span>', obj.guest_session, obj.guest_session[:18] + ('...' if len(obj.guest_session) > 18 else ''))
        return format_html('<span style="color: #999;">Тест / Не привязан</span>')


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('deal_id', 'snapshot', 'client', 'manager', 'amount', 'status', 'status_raw', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('deal_id', 'client', 'manager', 'contact')
    ordering = ('-created_at',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'snapshot', 'role', 'content_preview', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content',)
    ordering = ('-created_at',)

    def content_preview(self, obj):
        return (obj.content[:100] + '...') if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Содержание'
