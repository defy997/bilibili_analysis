"""
WSGI config for bilibili_analysis project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys

# 添加项目路径到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from django.core.wsgi import get_wsgi_application

# 检测运行环境
ENV = os.environ.get('DJANGO_SETTINGS_MODULE', '')

# 默认使用生产环境设置
if 'settings_production' in ENV or os.environ.get('DEBUG', '').lower() in ('false', '0', 'no'):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bilibili_analysis.settings_production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bilibili_analysis.settings")

application = get_wsgi_application()
