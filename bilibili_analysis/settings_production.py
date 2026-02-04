"""
Django settings for bilibili_analysis project - Production Environment
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ========== 生产环境核心配置 ==========
# 读取环境变量或使用默认值
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

# 安全设置：只允许指定的域名
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '10.0.0.2').split(',')

# 密钥管理：生产环境必须使用环境变量
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-y%&)nd6gy4b*b&b%f(z4!)2@98*vqv$i+79w(q+%^z+mozgnpd')

# ========== 安全中间件 ==========
MIDDLEWARE = [
    # 安全中间件（生产环境必备）
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS 配置（生产环境建议限制来源）
CORS_ALLOW_ALL_ORIGINS = DEBUG  # 生产环境关闭，改用白名单
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ========== 应用定义 ==========
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "analysis",
]

ROOT_URLCONF = "bilibili_analysis.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bilibili_analysis.wsgi.application"

# ========== 数据库配置 ==========
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get('DB_NAME', 'bilibili_analysis'),
        "USER": os.environ.get('DB_USER', 'root'),
        "PASSWORD": os.environ.get('DB_PASSWORD', '142857'),
        "HOST": os.environ.get('DB_HOST', '127.0.0.1'),
        "PORT": os.environ.get('DB_PORT', '3306'),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ========== 密码验证 ==========
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ========== 国际化 ==========
LANGUAGE_CODE = "zh-hans"  # 中文
TIME_ZONE = "Asia/Shanghai"  # 上海时区
USE_I18N = True
USE_TZ = True

# ========== 静态文件配置 ==========
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # 收集静态文件目录

# 额外静态文件目录
STATICFILES_DIRS = [
    # os.path.join(BASE_DIR, 'static'),
]

# WhiteNoise 配置（可选，用于直接服务静态文件）
# INSTALLED_APPS 添加 "whitenoise"
# MIDDLEWARE 添加 "whitenoise.middleware.WhiteNoiseMiddleware"

# ========== 会话配置 ==========
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 7天
SESSION_COOKIE_SECURE = not DEBUG  # 生产环境必须为 True
SESSION_COOKIE_HTTPONLY = True

# ========== 安全配置 ==========
# 生产环境必须启用
if not DEBUG:
    # HTTPS 配置
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Cookie 安全
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS 配置（可选，首次部署建议注释掉）
    # SECURE_HSTS_SECONDS = 31536000  # 1年
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True

# ========== 日志配置 ==========
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/bilibili_analysis.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ========== Email 配置 ==========
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.qq.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '2902523121@qq.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'BiliMood <2902523121@qq.com>')

# ========== Celery 配置 ==========
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_WORKER_POOL = 'solo'  # Windows 兼容
CELERY_WORKER_CONCURRENCY = 1

# ========== 默认主键 ==========
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
