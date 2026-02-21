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
    """获取用户等级分布（优化版）"""
    # 直接在数据库中分组统计，避免加载所有数据到内存
    distribution = Comment.objects.filter(
        video_id=bvid
    ).values('user_level').annotate(
        count=Count('rpid')
    ).order_by('user_level')

    return list(distribution)


def get_vip_distribution(bvid):
    """获取会员类型分布（优化版 - 单次聚合查询）"""
    from django.db.models import Case, When, IntegerField

    comments = Comment.objects.filter(video_id=bvid)

    # 使用条件聚合一次性获取所有统计
    stats = comments.aggregate(
        normal=Count('rpid', filter=Q(vip_type=0)),
        monthly_vip=Count('rpid', filter=Q(vip_type=1)),
        annual_vip=Count('rpid', filter=Q(vip_type=2))
    )

    return {
        "normal": stats['normal'],
        "monthly_vip": stats['monthly_vip'],
        "annual_vip": stats['annual_vip']
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
    获取用户画像仪表板数据（优化版 - 减少数据库查询次数）
    """
    try:
        video = Video.objects.get(bvid=bvid)

        # 使用单次聚合查询获取所有统计数据
        aggregated = Comment.objects.filter(video_id=bvid).aggregate(
            total_users=Count('mid', distinct=True),
            avg_level=Avg('user_level'),
            monthly_vip=Count('rpid', filter=Q(vip_type=1)),
            annual_vip=Count('rpid', filter=Q(vip_type=2))
        )

        total_users = aggregated['total_users'] or 0
        vip_total = (aggregated['monthly_vip'] or 0) + (aggregated['annual_vip'] or 0)
        avg_level = round(aggregated['avg_level'] or 0, 1)
        vip_ratio = round(vip_total / total_users * 100, 1) if total_users > 0 else 0

        # 获取分布数据
        level_dist = get_user_level_distribution(bvid)
        vip_dist = get_vip_distribution(bvid)

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
            "level_distribution": level_dist,
            "vip_distribution": vip_dist,
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


# ==================== 多模态情感融合分析 ====================

def get_multimodal_emotion_analysis(bvid, video_type='general'):
    """
    获取多模态情感分析结果
    融合音频、文本（评论）、弹幕的情感分析

    Args:
        bvid: 视频BV号
        video_type: 视频类型 ('music', 'tutorial', 'vlog', 'game', 'general')

    Returns:
        dict: 包含融合情感、注意力权重、冲突检测等信息
    """
    from .multimodal_attention import (
        adaptive_attention_fusion,
        detect_emotion_conflict
    )

    try:
        video = Video.objects.get(bvid=bvid)

        # 1. 获取文本情感（评论）
        comments = Comment.objects.filter(video_id=bvid)
        total_comments = comments.count()

        if total_comments > 0:
            text_positive = comments.filter(sentiment_label='positive').count() / total_comments
            text_neutral = comments.filter(sentiment_label='neutral').count() / total_comments
            text_negative = comments.filter(sentiment_label='negative').count() / total_comments
        else:
            text_positive = text_neutral = text_negative = 0.33

        text_emotion = {
            'positive': text_positive,
            'neutral': text_neutral,
            'negative': text_negative
        }

        # 2. 获取音频情感（从 AudioSentiment 表）
        from .models import AudioSentiment
        audio_sentiments = AudioSentiment.objects.filter(video=video)
        
        if audio_sentiments.exists():
            # 计算音频情感统计
            audio_positive_scores = []
            audio_negative_scores = []
            
            for audio in audio_sentiments:
                if audio.emotion_probs:
                    audio_positive_scores.append(
                        audio.emotion_probs.get('happy', 0) + audio.emotion_probs.get('surprise', 0)
                    )
                    audio_negative_scores.append(
                        audio.emotion_probs.get('angry', 0) + audio.emotion_probs.get('sad', 0) + audio.emotion_probs.get('fearful', 0)
                    )
            
            if audio_positive_scores:
                avg_positive = sum(audio_positive_scores) / len(audio_positive_scores)
                avg_negative = sum(audio_negative_scores) / len(audio_negative_scores)
                # 归一化
                total = avg_positive + avg_negative + 0.3  # 假设中立为0.3
                audio_emotion = {
                    'positive': avg_positive / total,
                    'neutral': 0.3 / total,
                    'negative': avg_negative / total
                }
            else:
                audio_emotion = {'positive': 0.5, 'neutral': 0.3, 'negative': 0.2}
        else:
            audio_emotion = {'positive': 0.5, 'neutral': 0.3, 'negative': 0.2}

        # 3. 获取弹幕情感
        danmus = Danmu.objects.filter(cid=video.cid)
        total_danmus = danmus.count()

        if total_danmus > 0:
            danmu_positive = danmus.filter(sentiment_label='positive').count() / total_danmus
            danmu_neutral = danmus.filter(sentiment_label='neutral').count() / total_danmus
            danmu_negative = danmus.filter(sentiment_label='negative').count() / total_danmus
        else:
            danmu_positive, danmu_neutral, danmu_negative = 0.5, 0.3, 0.2

        danmu_emotion = {
            'positive': danmu_positive,
            'neutral': danmu_neutral,
            'negative': danmu_negative
        }

        # 4. 使用自适应注意力融合
        fused_emotion, attention_weights = adaptive_attention_fusion(
            audio_emotion, text_emotion, danmu_emotion, video_type=video_type
        )

        # 5. 检测情感冲突
        conflict_info = detect_emotion_conflict(audio_emotion, text_emotion, danmu_emotion)

        # 6. 计算情感强度
        emotion_strength = max(fused_emotion.values()) - min(fused_emotion.values())

        # 7. 确定主导情感
        dominant_emotion = max(fused_emotion, key=fused_emotion.get)

        # 8. 计算综合得分（用于前端显示）
        overall_score = fused_emotion.get('positive', 0.5)

        # 9. 生成时间轴数据（模拟分段）
        time_segments = generate_time_segments(
            audio_sentiments, comments, video.cid, num_segments=10
        )

        # 10. 生成冲突详情（按时间段）
        conflicts = generate_conflict_details(
            time_segments, threshold=0.3
        )

        # 11. 获取详细音频情感分布（6分类）
        audio_emotion_detail = get_audio_emotion_detail(audio_sentiments)

        return {
            'success': True,
            'fused_emotion': {
                'positive': round(fused_emotion['positive'], 3),
                'neutral': round(fused_emotion['neutral'], 3),
                'negative': round(fused_emotion['negative'], 3)
            },
            'attention_weights': {
                'audio': round(attention_weights['audio'], 3),
                'text': round(attention_weights['text'], 3),
                'danmu': round(attention_weights['danmu'], 3)
            },
            'individual_emotions': {
                'audio': audio_emotion,
                'text': text_emotion,
                'danmu': danmu_emotion
            },
            'dominant_emotion': dominant_emotion,
            'emotion_strength': round(emotion_strength, 3),
            'conflict_info': conflict_info,
            'video_type': video_type,
            'metadata': {
                'total_comments': total_comments,
                'total_danmus': total_danmus,
                'total_audio_segments': audio_sentiments.count()
            },
            # 前端需要的字段
            'overallScore': overall_score,
            'textScore': text_emotion.get('positive', 0.5),
            'audioScore': audio_emotion.get('positive', 0.5),
            'timeSegments': time_segments,
            'conflicts': conflicts,
            'audioEmotions': audio_emotion_detail,
            'textEmotions': text_emotion
        }

    except Video.DoesNotExist:
        return {'success': False, 'error': 'Video not found'}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def generate_time_segments(audio_sentiments, comments, cid, num_segments=10):
    """生成时间轴分段数据"""
    segments = []
    
    # 获取视频大致时长（从音频分段推断）
    if audio_sentiments.exists():
        max_time = audio_sentiments.aggregate(Max('time_offset'))['time_offset__max'] or 600
    else:
        # 尝试从弹幕获取视频时长
        from .models import Danmu
        max_danmu_time = Danmu.objects.filter(cid=cid).aggregate(Max('progress'))['progress__max']
        max_time = max_danmu_time if max_danmu_time else 600
    
    segment_duration = max_time / num_segments
    
    # 获取评论发布时间分布
    comment_times = []
    for c in comments:
        if c.ctime:
            comment_times.append(c.ctime)
    
    for i in range(num_segments):
        start_time = i * segment_duration
        end_time = (i + 1) * segment_duration
        
        # 统计该时间段的评论数量作为文本情感权重
        segment_comments = [c for c in comments if c.ctime and 
                          start_time <= (c.ctime % 86400) < end_time]
        
        if segment_comments:
            # 计算该时间段评论的情感倾向
            pos_count = sum(1 for c in segment_comments if c.sentiment_label == 'positive')
            neg_count = sum(1 for c in segment_comments if c.sentiment_label == 'negative')
            total = len(segment_comments)
            
            text_score = (pos_count - neg_count) / total * 0.5 + 0.5  # 归一化到 0-1
        else:
            text_score = 0.5  # 默认中立
        
        # 查找对应时间段的音频情感
        audio_score = 0.5
        if audio_sentiments.exists():
            segment_audio = [a for a in audio_sentiments if 
                           a.time_offset and start_time <= a.time_offset < end_time]
            if segment_audio:
                pos = sum(a.emotion_probs.get('happy', 0) + a.emotion_probs.get('surprise', 0) 
                         for a in segment_audio)
                neg = sum(a.emotion_probs.get('angry', 0) + a.emotion_probs.get('sad', 0) + a.emotion_probs.get('fearful', 0)
                         for a in segment_audio)
                audio_score = (pos - neg) * 0.5 + 0.5
        
        # 计算权重（评论数量越多，文本权重越高）
        text_weight = min(0.8, 0.3 + len(segment_comments) * 0.05)
        audio_weight = 1 - text_weight
        
        segments.append({
            'time': int(start_time),
            'textScore': round(text_score, 3),
            'audioScore': round(audio_score, 3),
            'textWeight': round(text_weight, 3),
            'audioWeight': round(audio_weight, 3),
            'commentCount': len(segment_comments)
        })
    
    return segments


def generate_conflict_details(time_segments, threshold=0.3):
    """生成冲突详情"""
    conflicts = []
    
    for seg in time_segments:
        diff = abs(seg['textScore'] - seg['audioScore'])
        if diff > threshold:
            severity = 'critical' if diff > 0.5 else ('high' if diff > 0.4 else 'medium')
            conflicts.append({
                'time': seg['time'],
                'duration': 60,
                'severity': severity,
                'textScore': seg['textScore'],
                'audioScore': seg['audioScore']
            })
    
    return conflicts


def get_audio_emotion_detail(audio_sentiments):
    """获取音频情感详细分布（6分类）"""
    if not audio_sentiments.exists():
        return {
            'happy': 0.2,
            'neutral': 0.3,
            'sad': 0.15,
            'angry': 0.1,
            'fearful': 0.1,
            'surprise': 0.15
        }
    
    emotions = {'happy': [], 'neutral': [], 'sad': [], 'angry': [], 'fearful': [], 'surprise': []}
    
    for audio in audio_sentiments:
        if audio.emotion_probs:
            for emo, prob in audio.emotion_probs.items():
                if emo in emotions:
                    emotions[emo].append(prob)
    
    result = {}
    for emo, values in emotions.items():
        result[emo] = sum(values) / len(values) if values else 0.1
    
    # 归一化
    total = sum(result.values())
    if total > 0:
        result = {k: round(v / total, 3) for k, v in result.items()}
    
    return result
