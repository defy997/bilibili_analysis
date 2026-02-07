"""
数据分析和统计函数库
提供各类可视化所需的数据聚合功能
"""
from django.db.models import Count, Avg, Sum, Q, Max, Min
from django.db.models.functions import TruncHour, TruncDate
from .models import Comment, Danmu, Video
from datetime import datetime, timedelta


def get_sentiment_distribution(bvid):
    """获取情感分布统计"""
    comments = Comment.objects.filter(video_id=bvid)

    return {
        "positive": comments.filter(sentiment_label="positive").count(),
        "neutral": comments.filter(sentiment_label="neutral").count(),
        "negative": comments.filter(sentiment_label="negative").count()
    }


def get_sentiment_score_histogram(bvid, bins=10):
    """获取情感分数分布直方图数据"""
    comments = Comment.objects.filter(video_id=bvid).values_list('sentiment_score', flat=True)

    if not comments:
        return []

    # 创建分数区间
    histogram = []
    step = 1.0 / bins

    for i in range(bins):
        range_start = i * step
        range_end = (i + 1) * step
        count = sum(1 for score in comments if range_start <= score < range_end)

        histogram.append({
            "range": f"{range_start:.1f}-{range_end:.1f}",
            "count": count
        })

    return histogram


def get_sentiment_trend_by_time(bvid, interval='hour'):
    """获取按时间的情感趋势"""
    comments = Comment.objects.filter(video_id=bvid).exclude(ctime__isnull=True)

    if interval == 'hour':
        # 按小时统计
        trend_data = comments.annotate(
            time_bucket=TruncHour('ctime')
        ).values('time_bucket').annotate(
            positive=Count('rpid', filter=Q(sentiment_label='positive')),
            neutral=Count('rpid', filter=Q(sentiment_label='neutral')),
            negative=Count('rpid', filter=Q(sentiment_label='negative'))
        ).order_by('time_bucket')
    else:
        # 按天统计
        trend_data = comments.annotate(
            time_bucket=TruncDate('ctime')
        ).values('time_bucket').annotate(
            positive=Count('rpid', filter=Q(sentiment_label='positive')),
            neutral=Count('rpid', filter=Q(sentiment_label='neutral')),
            negative=Count('rpid', filter=Q(sentiment_label='negative'))
        ).order_by('time_bucket')

    return [
        {
            "time": item['time_bucket'].strftime('%Y-%m-%d %H:00' if interval == 'hour' else '%Y-%m-%d'),
            "positive": item['positive'],
            "neutral": item['neutral'],
            "negative": item['negative']
        }
        for item in trend_data
    ]


def get_user_level_distribution(bvid):
    """获取用户等级分布"""
    distribution = Comment.objects.filter(video_id=bvid).values('user_level').annotate(
        count=Count('rpid')
    ).order_by('user_level')

    return list(distribution)


def get_vip_distribution(bvid):
    """获取会员类型分布"""
    comments = Comment.objects.filter(video_id=bvid)

    # vip_type: 0=普通用户, 1=月度大会员, 2=年度大会员
    return {
        "normal": comments.filter(vip_type=0).count(),
        "monthly_vip": comments.filter(vip_type=1).count(),
        "annual_vip": comments.filter(vip_type=2).count()
    }


def get_top_users_by_likes(bvid, limit=10):
    """获取高赞用户Top榜单"""
    top_users = Comment.objects.filter(video_id=bvid).values('mid', 'uname').annotate(
        total_likes=Sum('like_count'),
        comment_count=Count('rpid')
    ).order_by('-total_likes')[:limit]

    return list(top_users)


def get_quality_score_distribution(bvid, bins=5):
    """获取质量评分分布"""
    scores = Comment.objects.filter(video_id=bvid).values_list('quality_score', flat=True)

    if not scores:
        return []

    histogram = []
    step = 1.0 / bins

    for i in range(bins):
        range_start = i * step
        range_end = (i + 1) * step
        count = sum(1 for score in scores if range_start <= score < range_end)

        histogram.append({
            "range": f"{range_start:.1f}-{range_end:.1f}",
            "count": count
        })

    return histogram


def get_cleaning_stats(bvid):
    """获取数据清洗统计"""
    total = Comment.objects.filter(video_id=bvid).count()
    duplicates = Comment.objects.filter(video_id=bvid, is_duplicate=True).count()

    return {
        "total_raw": total,
        "after_dedup": total - duplicates,
        "duplicate_count": duplicates,
        "dedup_rate": round(duplicates / total * 100, 2) if total > 0 else 0
    }


def get_top_comments(bvid, limit=20):
    """获取高赞评论Top榜单"""
    comments = Comment.objects.filter(video_id=bvid).order_by('-like_count')[:limit]

    return [
        {
            "rpid": c.rpid,
            "message": c.message,
            "like_count": c.like_count,
            "uname": c.uname,
            "sentiment_label": c.sentiment_label,
            "sentiment_score": round(c.sentiment_score, 3),
            "quality_score": round(c.quality_score, 3),
            "ctime": c.ctime.strftime('%Y-%m-%d %H:%M') if c.ctime else None
        }
        for c in comments
    ]


def get_hourly_distribution(bvid):
    """获取24小时评论分布（0-23点）"""
    comments = Comment.objects.filter(video_id=bvid).exclude(ctime__isnull=True)

    # 按小时分组
    hourly = [0] * 24
    for comment in comments:
        hour = comment.ctime.hour
        hourly[hour] += 1

    return [{"hour": i, "count": hourly[i]} for i in range(24)]


def get_daily_trend(bvid):
    """获取按天的评论趋势"""
    trend = Comment.objects.filter(video_id=bvid).exclude(ctime__isnull=True).annotate(
        date=TruncDate('ctime')
    ).values('date').annotate(
        count=Count('rpid'),
        avg_sentiment=Avg('sentiment_score')
    ).order_by('date')

    return [
        {
            "date": item['date'].strftime('%Y-%m-%d'),
            "count": item['count'],
            "avg_sentiment": round(item['avg_sentiment'], 3) if item['avg_sentiment'] else 0.5
        }
        for item in trend
    ]


def get_location_distribution(bvid, limit=10):
    """获取地域分布Top榜单"""
    locations = Comment.objects.filter(video_id=bvid).exclude(
        location__isnull=True
    ).exclude(
        location=''
    ).values('location').annotate(
        count=Count('rpid')
    ).order_by('-count')[:limit]

    return [
        {
            "province": item['location'],
            "value": item['count']
        }
        for item in locations
    ]


def get_danmu_timeline_heatmap(bvid, interval=60):
    """获取弹幕时间轴热度图（按视频时间）"""
    try:
        video = Video.objects.get(bvid=bvid)
        danmus = Danmu.objects.filter(cid=video.cid).order_by('video_time')

        if not danmus.exists():
            return []

        # 获取视频最大时间
        max_time = danmus.aggregate(Max('video_time'))['video_time__max']
        if max_time is None:
            return []

        # 按间隔（默认60秒）分组统计
        buckets = int(max_time / interval) + 1
        heatmap = []

        for i in range(buckets):
            start_time = i * interval
            end_time = (i + 1) * interval

            bucket_danmus = danmus.filter(
                video_time__gte=start_time,
                video_time__lt=end_time
            )

            count = bucket_danmus.count()
            avg_sentiment = bucket_danmus.aggregate(Avg('sentiment_score'))['sentiment_score__avg']

            heatmap.append({
                "time": start_time,
                "count": count,
                "sentiment_avg": round(avg_sentiment, 3) if avg_sentiment else 0.5
            })

        return heatmap

    except Video.DoesNotExist:
        return []


def get_danmu_stats(bvid):
    """获取弹幕基础统计"""
    try:
        video = Video.objects.get(bvid=bvid)
        danmus = Danmu.objects.filter(cid=video.cid)

        return {
            "total_count": danmus.count(),
            "positive": danmus.filter(sentiment_label="positive").count(),
            "neutral": danmus.filter(sentiment_label="neutral").count(),
            "negative": danmus.filter(sentiment_label="negative").count()
        }
    except Video.DoesNotExist:
        return {
            "total_count": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0
        }


def get_user_profile_dashboard(bvid):
    """
    获取用户画像仪表板数据
    """
    try:
        video = Video.objects.get(bvid=bvid)
        comments = Comment.objects.filter(video_id=bvid)
        total_users = comments.values('mid').distinct().count()

        # 会员分布
        vip = get_vip_distribution(bvid)
        vip_total = vip['monthly_vip'] + vip['annual_vip']
        vip_ratio = round(vip_total / total_users * 100, 1) if total_users > 0 else 0

        # 平均用户等级
        avg_level = comments.aggregate(avg=Avg('user_level'))['avg']
        avg_level = round(avg_level, 1) if avg_level else 0

        return {
            "success": True,
            "video_info": {
                "bvid": video.bvid,
                "title": video.title,
            },
            "overview_stats": {
                "total_users": total_users,
                "vip_ratio": vip_ratio,
                "avg_level": avg_level,
            },
            "level_distribution": get_user_level_distribution(bvid),
            "vip_distribution": vip,
            "location_distribution": get_location_distribution(bvid, limit=15),
            "top_users": get_top_users_by_likes(bvid, limit=10),
        }
    except Video.DoesNotExist:
        return {
            "success": False,
            "error": "Video not found"
        }


def get_comprehensive_dashboard(bvid):
    """
    获取综合仪表板数据（一次性返回所有可视化数据）
    """
    try:
        video = Video.objects.get(bvid=bvid)

        dashboard_data = {
            "success": True,
            "video_info": {
                "bvid": video.bvid,
                "title": video.title,
                "pubdate": video.pubdate.strftime('%Y-%m-%d %H:%M') if video.pubdate else None
            },

            # 1. 情感分析数据
            "sentiment": {
                "distribution": get_sentiment_distribution(bvid),
                "score_histogram": get_sentiment_score_histogram(bvid, bins=10),
                "trend_by_time": get_sentiment_trend_by_time(bvid, interval='hour')
            },

            # 2. 用户画像数据
            "user_profile": {
                "level_distribution": get_user_level_distribution(bvid),
                "vip_distribution": get_vip_distribution(bvid),
                "top_users": get_top_users_by_likes(bvid, limit=10)
            },

            # 3. 内容质量数据
            "quality": {
                "score_distribution": get_quality_score_distribution(bvid, bins=5),
                "cleaning_stats": get_cleaning_stats(bvid),
                "top_comments": get_top_comments(bvid, limit=20)
            },

            # 4. 时间维度数据
            "time_analysis": {
                "hourly_distribution": get_hourly_distribution(bvid),
                "daily_trend": get_daily_trend(bvid)
            },

            # 5. 地域数据
            "location": {
                "top_provinces": get_location_distribution(bvid, limit=10)
            },

            # 6. 弹幕数据
            "danmu": {
                "stats": get_danmu_stats(bvid),
                "timeline_heatmap": get_danmu_timeline_heatmap(bvid, interval=60)
            }
        }

        return dashboard_data

    except Video.DoesNotExist:
        return {
            "success": False,
            "error": "Video not found"
        }
