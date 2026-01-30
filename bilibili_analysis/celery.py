import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_analysis.settings')
app = Celery('bilibili_analysis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
