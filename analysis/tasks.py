from celery import shared_task


@shared_task
def analyze_sentiment_chunk(text_chunk):
    """单个 Worker 处理一个 chunk"""
    from .sentiment_model import SentimentModel
    model = SentimentModel()  # 单例，每个 Worker 进程只加载一次
    return model.predict(text_chunk)
