"""
URL configuration for bilibili_analysis project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from analysis.views import analyze_by_bvid, video_dashboard, get_config, save_config
from analysis.auth_views import send_code, register, login, logout, check_login

def index(request):
    return JsonResponse({"message": "BiliMood API Server", "version": "1.0"})

urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("api/analyze/", analyze_by_bvid),
    path("api/video/dashboard/<str:bvid>/", video_dashboard, name="video_dashboard"),
    path("api/config/", get_config, name="get_config"),
    path("api/config/save/", save_config, name="save_config"),

    # 用户认证相关
    path("api/auth/send-code/", send_code, name="send_code"),
    path("api/auth/register/", register, name="register"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/check/", check_login, name="check_login"),
]
