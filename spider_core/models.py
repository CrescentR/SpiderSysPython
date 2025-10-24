from django.db import models


class SpiderTask(models.Model):
    """简化的爬虫任务模型 - 专注于关键词搜索"""
    STATUS_CHOICES = [
        ('created', '已创建'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='任务名称')
    keywords = models.CharField(max_length=255, verbose_name='搜索关键词')
    description=models.CharField(max_length=500, blank=True, verbose_name='任务描述')
    max_pages = models.IntegerField(default=1, verbose_name='搜索页数')
    search_engine = models.CharField(
        max_length=10, 
        choices=[('bing', 'Bing'), ('baidu', '百度')], 
        default='bing', 
        verbose_name='搜索引擎'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    class Meta:
        verbose_name = '爬虫任务'
        verbose_name_plural = '爬虫任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.keywords}"


class CrawledResult(models.Model):
    """爬取结果模型 - 存储搜索到的链接"""
    task = models.ForeignKey(SpiderTask, on_delete=models.CASCADE, related_name='results', verbose_name='所属任务')
    title = models.CharField(max_length=500, verbose_name='页面标题')
    url = models.URLField(max_length=2000, verbose_name='页面URL')
    description = models.TextField(blank=True, verbose_name='页面描述')
    crawled_at = models.DateTimeField(auto_now_add=True, verbose_name='爬取时间')
    
    class Meta:
        verbose_name = '爬取结果'
        verbose_name_plural = '爬取结果'
        ordering = ['-crawled_at']
        unique_together = ['task', 'url']  # 同一任务中URL唯一
    
    def __str__(self):
        return f"{self.task.name} - {self.title}"
