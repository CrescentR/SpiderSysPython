from django.urls import path, include
from . import views

app_name = 'spider_core'
urlpatterns = [
    path('', views.index, name='index'),
    path('api/crawl/start', views.start_crawl, name='start_crawl'),
    path('api/crawl/stop/<int:task_id>', views.stop_crawl, name='stop_crawl'),
    path('api/crawl/stream/<int:task_id>', views.stream_results, name='stream_results'),
    path('api/crawl/debug/<int:task_id>', views.debug_publish, name='debug_publish'),
    path('api/queues/info', views.queue_info, name='queue_info'),
]