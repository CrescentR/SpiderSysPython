from django.contrib import admin
from .models import SpiderTask, CrawledResult


@admin.register(SpiderTask)
class SpiderTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'keywords', 'search_engine', 'created_at']
    list_filter = ['status', 'search_engine', 'created_at']
    search_fields = ['name', 'keywords']
    readonly_fields = ['created_at', 'started_at', 'completed_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'keywords', 'search_engine', 'max_pages', 'status')
        }),
        ('时间信息', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CrawledResult)
class CrawledResultAdmin(admin.ModelAdmin):
    list_display = ['task', 'title', 'url', 'crawled_at']
    list_filter = ['task', 'crawled_at']
    search_fields = ['title', 'url', 'description']
    readonly_fields = ['crawled_at']
