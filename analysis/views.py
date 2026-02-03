import json
import requests
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .services import process_video, check_need_refresh, crawl_video_info, crawl_audio_url
from .analytics import get_comprehensive_dashboard, get_user_profile_dashboard
from .models import UserConfig, Video, Comment, Danmu, AudioSentiment

# B站 Cookie（临时硬编码，后续从数据库读取）
BILI_COOKIE = "SESSDATA=b946e8f1%2C1785116159%2C0eabf%2A11CjBctKZ6g7g6nHZ7Oy_m31LUSM7SgaxXkfPZNvsn78ZoqBybck-zwkKuFL761GGZRFQSVkhrVjM3M2s4MWRheHJESkxMU1FSLVBQd1N0T1VxSE95YVVXenI3T28wSHFXaF9jSTlycjZDNkRva0hWM01PREpNMjQtRUF4NHlHUlVhbXp0dlJqOU5RIIEC"


@csrf_exempt
def analyze_by_bvid(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bvid = data.get('videoBvid')

            if not bvid:
                return JsonResponse({"error": "BVID is required"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Invalid request:{str(e)}"}, status=400)

        headers = {
            'authority': 'api.bilibili.com',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.bilibili.com/',
            'cookie': BILI_COOKIE,
        }

        try:
            # 调用服务层处理视频
            result = process_video(bvid, headers, BILI_COOKIE)

            if result.get("status") == "no_data":
                return JsonResponse({
                    "success": True,
                    "data": {"positive_count": 0, "neutral_count": 0, "negative_count": 0},
                    "video_info": {"title": "未知"}
                })

            return JsonResponse({
                "success": True,
                "data": {
                    "positive_count": result["positive_count"],
                    "neutral_count": result["neutral_count"],
                    "negative_count": result["negative_count"]
                },
                "video_info": {
                    "title": result["title"]
                }
            })

        except Exception as e:
            print(f"发生错误: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": f"发生错误: {str(e)}"}, status=500)
    else:
        return HttpResponseNotAllowed(['POST'])


@csrf_exempt
def video_dashboard(request, bvid):
    """
    综合仪表板接口 - 返回所有可视化数据
    GET /api/video/dashboard/<bvid>/
    如果视频不存在，自动触发分析流程
    """
    if request.method == 'GET':
        try:
            print(f"[Dashboard] 请求视频: {bvid}")

            headers = {
                'authority': 'api.bilibili.com',
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.bilibili.com/',
                'cookie': BILI_COOKIE,
            }

            # 检查是否需要刷新数据（对比远程评论数与本地评论数）
            try:
                need_refresh, _ = check_need_refresh(bvid, headers, BILI_COOKIE)
            except Exception:
                from .models import Video
                need_refresh = not Video.objects.filter(bvid=bvid).exists()

            if need_refresh:
                print(f"[Dashboard] 数据需要刷新，开始分析: {bvid}")
                try:
                    result = process_video(bvid, headers, BILI_COOKIE)
                    print(f"[Dashboard] 视频分析完成: {bvid}")

                    if result.get("status") == "no_data":
                        return JsonResponse({
                            "success": False,
                            "error": "Video has no data to analyze"
                        }, status=404)

                except Exception as analysis_error:
                    print(f"[Dashboard] 分析失败: {analysis_error}")
                    import traceback
                    traceback.print_exc()
                    return JsonResponse({
                        "success": False,
                        "error": f"Failed to analyze video: {str(analysis_error)}"
                    }, status=500)

            # 获取 dashboard 数据
            dashboard_data = get_comprehensive_dashboard(bvid)

            if not dashboard_data.get("success"):
                print(f"[Dashboard] 数据获取失败: {bvid}")
                return JsonResponse({
                    "success": False,
                    "error": "Failed to get dashboard data"
                }, status=500)

            print(f"[Dashboard] 数据获取成功，准备返回")
            return JsonResponse(dashboard_data, safe=False)

        except Exception as e:
            print(f"[Dashboard] 错误详情: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False,
                "error": f"Server error: {str(e)}"
            }, status=500)
    else:
        return HttpResponseNotAllowed(['GET'])


@csrf_exempt
def user_profile_dashboard(request, bvid):
    """
    用户画像接口
    GET /api/video/user-profile/<bvid>/
    """
    if request.method == 'GET':
        try:
            headers = {
                'authority': 'api.bilibili.com',
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.bilibili.com/',
                'cookie': BILI_COOKIE,
            }

            try:
                need_refresh, _ = check_need_refresh(bvid, headers, BILI_COOKIE)
            except Exception:
                from .models import Video
                need_refresh = not Video.objects.filter(bvid=bvid).exists()

            if need_refresh:
                try:
                    result = process_video(bvid, headers, BILI_COOKIE)
                    if result.get("status") == "no_data":
                        return JsonResponse({
                            "success": False,
                            "error": "Video has no data to analyze"
                        }, status=404)
                except Exception as analysis_error:
                    return JsonResponse({
                        "success": False,
                        "error": f"Failed to analyze video: {str(analysis_error)}"
                    }, status=500)

            dashboard_data = get_user_profile_dashboard(bvid)

            if not dashboard_data.get("success"):
                return JsonResponse({
                    "success": False,
                    "error": "Failed to get user profile data"
                }, status=500)

            return JsonResponse(dashboard_data, safe=False)

        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": f"Server error: {str(e)}"
            }, status=500)
    else:
        return HttpResponseNotAllowed(['GET'])


@csrf_exempt
def video_audio_dashboard(request, bvid):
    """
    视频音频分析仪表板
    GET  /api/video/audio-dashboard/<bvid>/ — 返回已有数据 + status
    POST /api/video/audio-dashboard/<bvid>/ — 触发异步分析
    """
    headers = {
        'authority': 'api.bilibili.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.bilibili.com/',
        'cookie': BILI_COOKIE,
    }

    if request.method == 'GET':
        try:
            # Ensure video exists in DB
            try:
                video = Video.objects.get(bvid=bvid)
            except Video.DoesNotExist:
                try:
                    result = process_video(bvid, headers, BILI_COOKIE)
                    if result.get("status") == "no_data":
                        return JsonResponse({"success": False, "error": "Video has no data"}, status=404)
                    video = Video.objects.get(bvid=bvid)
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)}, status=500)

            # Check for existing audio sentiment data
            audio_sentiments = AudioSentiment.objects.filter(video=video)
            timeline = []
            audio_avg = None
            audio_info = {}

            if audio_sentiments.exists():
                timeline = [
                    {
                        "time": s.time_offset,
                        "score": s.sentiment_score,
                        "label": s.sentiment_label,
                        "emotion": max(s.emotion_probs, key=s.emotion_probs.get) if s.emotion_probs else "",
                        "probabilities": s.emotion_probs,
                        "segment_duration": s.segment_duration,
                    }
                    for s in audio_sentiments
                ]
                from django.db.models import Avg
                audio_avg = audio_sentiments.aggregate(avg=Avg('sentiment_score'))['avg']
                audio_status = "analyzed"
            else:
                audio_status = "ready"
                try:
                    audio_info = crawl_audio_url(bvid, video.cid, headers, BILI_COOKIE)
                except Exception:
                    audio_info = {}

            # Calculate comparison data
            from django.db.models import Avg, Count, Q
            comment_qs = Comment.objects.filter(video=video)
            danmu_qs = Danmu.objects.filter(cid=video.cid)

            comment_avg = comment_qs.aggregate(avg=Avg('sentiment_score'))['avg']
            danmu_avg = danmu_qs.aggregate(avg=Avg('sentiment_score'))['avg']

            # 各类别数量统计（positive>=0.6, negative<=0.4, 其余neutral）
            def count_sentiments(qs):
                agg = qs.aggregate(
                    positive=Count('id', filter=Q(sentiment_score__gte=0.6)),
                    negative=Count('id', filter=Q(sentiment_score__lte=0.4)),
                    total=Count('id'),
                )
                agg['neutral'] = agg['total'] - agg['positive'] - agg['negative']
                return agg

            comment_dist = count_sentiments(comment_qs) if comment_qs.exists() else {'positive': 0, 'neutral': 0, 'negative': 0}
            danmu_dist = count_sentiments(danmu_qs) if danmu_qs.exists() else {'positive': 0, 'neutral': 0, 'negative': 0}

            if audio_sentiments.exists():
                audio_dist = count_sentiments(audio_sentiments)
            else:
                audio_dist = {'positive': 0, 'neutral': 0, 'negative': 0}

            return JsonResponse({
                "success": True,
                "video_info": {"title": video.title, "bvid": bvid},
                "audio": {
                    "audio_url": audio_info.get('audio_url', '') if audio_status == 'ready' else '',
                    "status": audio_status,
                    "timeline": timeline
                },
                "comparison": {
                    "comment_avg_sentiment": round(comment_avg, 3) if comment_avg else None,
                    "danmu_avg_sentiment": round(danmu_avg, 3) if danmu_avg else None,
                    "audio_avg_sentiment": round(audio_avg, 3) if audio_avg else None
                },
                "distribution": {
                    "audio": [audio_dist['positive'], audio_dist['neutral'], audio_dist['negative']],
                    "comments": [comment_dist['positive'], comment_dist['neutral'], comment_dist['negative']],
                    "danmu": [danmu_dist['positive'], danmu_dist['neutral'], danmu_dist['negative']],
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            force_refresh = data.get('force_refresh', False)

            # 检查缓存
            try:
                video = Video.objects.get(bvid=bvid)
                existing = AudioSentiment.objects.filter(video=video)
                if existing.exists() and not force_refresh:
                    timeline = [
                        {
                            "time": s.time_offset,
                            "score": s.sentiment_score,
                            "label": s.sentiment_label,
                            "probabilities": s.emotion_probs,
                            "segment_duration": s.segment_duration,
                        }
                        for s in existing
                    ]
                    return JsonResponse({
                        "success": True,
                        "status": "cached",
                        "timeline": timeline,
                    })
                if force_refresh and existing.exists():
                    existing.delete()
            except Video.DoesNotExist:
                pass

            # 优先 Celery 异步，Redis 不可达时同步回退
            celery_available = False
            try:
                import redis as _redis
                _r = _redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
                _r.ping()
                celery_available = True
            except Exception:
                pass

            if celery_available:
                from .tasks import analyze_audio_task
                task = analyze_audio_task.delay(bvid, BILI_COOKIE)
                return JsonResponse({
                    "success": True,
                    "status": "processing",
                    "task_id": task.id,
                })
            else:
                print("Redis 不可达，同步执行音频分析")
                from .services import analyze_video_audio
                result = analyze_video_audio(bvid, headers, BILI_COOKIE)
                return JsonResponse({
                    "success": True,
                    "status": "completed",
                    "result": result,
                })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    else:
        return HttpResponseNotAllowed(['GET', 'POST'])


@csrf_exempt
def audio_task_status(request, task_id):
    """
    查询异步音频分析任务状态
    GET /api/video/audio-task/<task_id>/
    """
    if request.method == 'GET':
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": result.status,
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)

        return JsonResponse(response)
    else:
        return HttpResponseNotAllowed(['GET'])


@csrf_exempt
def get_config(request):
    """获取用户配置"""
    if request.method == 'GET':
        try:
            # 检查用户是否登录
            user_id = request.session.get('user_id')
            if not user_id:
                # 未登录，返回默认配置
                from .models import User
                default_user = User()  # 临时对象，使用默认值
                return JsonResponse({
                    "success": True,
                    "logged_in": False,
                    "data": default_user.get_config()
                })

            # 已登录，返回用户配置
            from .models import User
            user = User.objects.get(id=user_id)
            return JsonResponse({
                "success": True,
                "logged_in": True,
                "data": user.get_config()
            })
        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=500)
    else:
        return HttpResponseNotAllowed(['GET'])


@csrf_exempt
def save_config(request):
    """保存用户配置"""
    if request.method == 'POST':
        try:
            # 检查用户是否登录
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({
                    "success": False,
                    "message": "请先登录"
                }, status=401)

            from .models import User
            user = User.objects.get(id=user_id)
            data = json.loads(request.body)

            # 更新过滤配置
            filter_config = data.get('filter_config', {})
            if 'min_length' in filter_config:
                user.min_length = filter_config['min_length']
            if 'max_length' in filter_config:
                user.max_length = filter_config['max_length']
            if 'min_chinese_ratio' in filter_config:
                user.min_chinese_ratio = filter_config['min_chinese_ratio']
            if 'min_quality_score' in filter_config:
                user.min_quality_score = filter_config['min_quality_score']
            if 'dedup_method' in filter_config:
                user.dedup_method = filter_config['dedup_method']
            if 'fuzzy_threshold' in filter_config:
                user.fuzzy_threshold = filter_config['fuzzy_threshold']
            if 'embedding_threshold' in filter_config:
                user.embedding_threshold = filter_config['embedding_threshold']
            if 'max_char_repeat' in filter_config:
                user.max_char_repeat = filter_config['max_char_repeat']
            if 'min_unique_ratio' in filter_config:
                user.min_unique_ratio = filter_config['min_unique_ratio']
            if 'min_unique_check_length' in filter_config:
                user.min_unique_check_length = filter_config['min_unique_check_length']

            # 更新白名单配置
            whitelist_config = data.get('whitelist_config', {})
            if 'high_like_threshold' in whitelist_config:
                user.high_like_threshold = whitelist_config['high_like_threshold']
            if 'high_reply_threshold' in whitelist_config:
                user.high_reply_threshold = whitelist_config['high_reply_threshold']
            if 'combined_like_threshold' in whitelist_config:
                user.combined_like_threshold = whitelist_config['combined_like_threshold']
            if 'combined_reply_threshold' in whitelist_config:
                user.combined_reply_threshold = whitelist_config['combined_reply_threshold']

            # 更新UI配置
            ui_config = data.get('ui_config', {})
            if 'background_color' in ui_config:
                user.background_color = ui_config['background_color']
            if 'opacity' in ui_config:
                user.opacity = ui_config['opacity']

            user.save()

            return JsonResponse({
                "success": True,
                "message": "配置保存成功",
                "data": user.get_config()
            })
        except Exception as e:
            print(f"保存配置失败: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False,
                "error": str(e)
            }, status=500)
    else:
        return HttpResponseNotAllowed(['POST'])
