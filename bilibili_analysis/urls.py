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
from analysis.views import analyze_by_bvid, video_dashboard, user_profile_dashboard, video_audio_dashboard, audio_task_status, get_config, save_config, async_analyze_video, task_status
from analysis.views import check_sessdata, refresh_sessdata, generate_qrcode, poll_login, get_cookie_header
from analysis.auth_views import send_code, register, login, logout, check_login

def index(request):
    return JsonResponse({"message": "BiliMood API Server", "version": "1.0"})

urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("api/analyze/", analyze_by_bvid),

    # 视频分析接口
    path("api/video/async-analyze/", async_analyze_video, name="async_analyze_video"),
    path("api/video/task-status/", task_status, name="task_status"),
    path("api/video/dashboard/<str:bvid>/", video_dashboard, name="video_dashboard"),
    path("api/video/user-profile/<str:bvid>/", user_profile_dashboard, name="user_profile_dashboard"),
    path("api/video/audio-dashboard/<str:bvid>/", video_audio_dashboard, name="video_audio_dashboard"),
    path("api/video/audio-task/<str:task_id>/", audio_task_status, name="audio_task_status"),

    # 配置接口
    path("api/config/", get_config, name="get_config"),
    path("api/config/save/", save_config, name="save_config"),

    # 用户认证相关
    path("api/auth/send-code/", send_code, name="send_code"),
    path("api/auth/register/", register, name="register"),
    path("api/auth/login/", login, name="login"),
    path("api/auth/logout/", logout, name="logout"),
    path("api/auth/check/", check_login, name="check_login"),

    # B站 SESSDATA 管理
    path("api/sessdata/check/", check_sessdata, name="check_sessdata"),
    path("api/sessdata/refresh/", refresh_sessdata, name="refresh_sessdata"),
    path("api/sessdata/qrcode/", generate_qrcode, name="generate_qrcode"),
    path("api/sessdata/poll/", poll_login, name="poll_login"),
    path("api/sessdata/cookie/", get_cookie_header, name="get_cookie_header"),
]
