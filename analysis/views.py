import json
import requests
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .services import process_video

# Create your views here.
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
