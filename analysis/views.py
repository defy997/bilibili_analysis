import json
import requests
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .services import process_video
from .analytics import get_comprehensive_dashboard
from .models import UserConfig

# B站 Cookie（临时硬编码，后续从数据库读取）
BILI_COOKIE = "SESSDATA=9d152316%2C1784773229%2Cf7490%2A12CjA977l9BccQUeqHZrB3ZqChrOlOXKFQ8Kti5_wGgZ3oITJclsdPgXJiw9zi5S2JsiMSVllkNGsyY3d2TVB2eFl6dU84ckZ3dk9DQU9Zb21xS3U4cUMxMUE1WURXaXFsQjhtby1sd0VRdlptX0x4WFZsa3FLSzBiNU0tVGVBWlJaUVBqTDBEZGZRIIEC"


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

            # 检查视频是否存在于数据库
            from .models import Video

            if not Video.objects.filter(bvid=bvid).exists():
                print(f"[Dashboard] 视频不存在，开始自动分析: {bvid}")

                # 准备请求头
                headers = {
                    'authority': 'api.bilibili.com',
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'zh-CN,zh;q=0.9',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'referer': 'https://www.bilibili.com/',
                    'cookie': BILI_COOKIE,
                }

                # 调用分析流程
                try:
                    result = process_video(bvid, headers, BILI_COOKIE)
                    print(f"[Dashboard] 视频分析完成: {bvid}")

                    if result.get("status") == "no_data":
                        print(f"[Dashboard] 视频无数据: {bvid}")
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
