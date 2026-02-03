from celery import shared_task


@shared_task
def analyze_sentiment_chunk(text_chunk):
    """单个 Worker 处理一个 chunk"""
    from .sentiment_model import SentimentModel
    model = SentimentModel()  # 单例，每个 Worker 进程只加载一次
    return model.predict(text_chunk)


@shared_task(bind=True)
def analyze_audio_task(self, bvid, cookie):
    """
    异步音频情感分析任务

    :param bvid: 视频BV号
    :param cookie: B站Cookie
    :return: timeline 数据
    """
    headers = {
        'authority': 'api.bilibili.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.bilibili.com/',
        'cookie': cookie,
    }

    from .services import analyze_video_audio
    result = analyze_video_audio(bvid, headers, cookie)
    return result
