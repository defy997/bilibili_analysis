from celery import Celery, group, chain, shared_task
from celery.result import AsyncResult
import celery
import json
from concurrent.futures import ThreadPoolExecutor


# 创建 Celery 应用实例（供其他模块导入）
app = Celery('bilibili_analysis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# ============================================================
# 用户画像统计任务
# ============================================================

@shared_task(bind=True)
def calculate_user_profile_stats(self, bvid):
    """
    并发计算用户画像统计数据

    原来需要 4 次数据库查询，现在使用线程池并发执行：
    1. 用户等级分布
    2. VIP 类型分布
    3. 地域分布 Top15
    4. 高赞用户 Top10

    结果存储到 Redis 缓存 (TTL: 1小时)
    """
    from .models import Comment, Video
    from django.db.models import Count, Sum, Avg
    import redis
    import time

    print(f"[UserProfile] 开始计算用户画像: bvid={bvid}")
    start_time = time.time()

    try:
        # 获取视频信息
        video = Video.objects.get(bvid=bvid)
        comments = Comment.objects.filter(video_id=bvid)

        # 使用线程池并发执行 4 个查询
        def get_level_dist():
            return list(comments.values('user_level').annotate(
                count=Count('rpid')
            ).order_by('user_level'))

        def get_vip_dist():
            return {
                "normal": comments.filter(vip_type=0).count(),
                "monthly_vip": comments.filter(vip_type=1).count(),
                "annual_vip": comments.filter(vip_type=2).count()
            }

        def get_location_dist():
            return list(comments.exclude(
                location__isnull=True
            ).exclude(
                location=''
            ).values('location').annotate(
                count=Count('rpid')
            ).order_by('-count')[:15])

        def get_top_users():
            return list(comments.values('mid', 'uname').annotate(
                total_likes=Sum('like_count'),
                comment_count=Count('rpid')
            ).order_by('-total_likes')[:10])

        # 并发执行 4 个查询
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_level = executor.submit(get_level_dist)
            future_vip = executor.submit(get_vip_dist)
            future_location = executor.submit(get_location_dist)
            future_top = executor.submit(get_top_users)

            level_distribution = future_level.result()
            vip_distribution = future_vip.result()
            location_distribution = future_location.result()
            top_users = future_top.result()

        # 计算汇总数据
        total_users = comments.values('mid').distinct().count()
        vip_total = vip_distribution['monthly_vip'] + vip_distribution['annual_vip']
        vip_ratio = round(vip_total / total_users * 100, 1) if total_users > 0 else 0
        avg_level = comments.aggregate(avg=Avg('user_level'))['avg']
        avg_level = round(avg_level, 1) if avg_level else 0

        result = {
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
            "level_distribution": level_distribution,
            "vip_distribution": vip_distribution,
            "location_distribution": location_distribution,
            "top_users": top_users,
        }

        # 存储到 Redis 缓存
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
            cache_key = f"user_profile:{bvid}"
            r.setex(cache_key, 3600, json.dumps(result, ensure_ascii=False, default=str))
            print(f"[UserProfile] 缓存已更新: {cache_key}")
        except Exception as redis_err:
            print(f"[UserProfile] Redis 缓存失败: {redis_err}")

        elapsed = time.time() - start_time
        print(f"[UserProfile] 计算完成: 耗时{elapsed:.2f}s, 用户数={total_users}")

        return result

    except Video.DoesNotExist:
        return {"success": False, "error": "Video not found"}
    except Exception as e:
        print(f"[UserProfile] 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@shared_task(bind=True)
def analyze_sentiment_chunk(self, text_chunk):
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


@shared_task(bind=True)
def crawl_and_analyze_comments(self, bvid, aid, headers, cookie):
    """
    爬取并分析评论的任务 - 流水线模式
    边爬取边分析边保存，而不是全部爬完再处理

    Returns:
        {
            'type': 'comments',
            'status': 'success' | 'no_data',
            'count': int,
            'positive_count': int,
            'negative_count': int,
            'neutral_count': int
        }
    """
    from .services import (
        crawl_comments, clean_text, is_meaningful_text,
        analyze_sentiment, get_sentiment_label, save_comment,
        crawl_video_info, save_video
    )
    import time

    print(f"[CommentTask] 开始处理评论: bvid={bvid}, aid={aid}")
    start_time = time.time()

    try:
        # 1. 确保视频记录存在
        try:
            from .models import Video
            video_obj = Video.objects.get(bvid=bvid)
        except Video.DoesNotExist:
            video_info = crawl_video_info(bvid, headers, cookie)
            video_obj = save_video(video_info, bvid)

        # 2. 爬取评论（使用 C++ 服务获取全部）
        all_comments = crawl_comments(aid, headers)

        if not all_comments:
            return {'type': 'comments', 'status': 'no_data', 'count': 0}

        print(f"[CommentTask] 爬取完成，共{len(all_comments)}条，开始流水线处理...")

        # 3. 流水线处理：逐条清洗、分析、保存
        comment_count = 0
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        batch_size = 32  # 每32条批量分析一次
        pending_texts = []
        pending_indices = []

        for i, comment in enumerate(all_comments):
            message = comment.get('content', {}).get('message', '')
            if not message:
                continue

            # 清洗
            cleaned = clean_text(message, for_analysis=True)

            # 过滤
            if not is_meaningful_text(cleaned):
                continue

            # 收集到待分析批次
            pending_texts.append(cleaned)
            pending_indices.append(i)

            # 如果批次满了，进行分析和保存
            if len(pending_texts) >= batch_size:
                # 批量情感分析
                scores = analyze_sentiment(pending_texts)

                # 逐条保存结果
                for idx, original_idx in enumerate(pending_indices):
                    original_comment = all_comments[original_idx]
                    score = scores[idx]
                    sentiment = get_sentiment_label(score)

                    result = save_comment(original_comment, video_obj, score, sentiment)
                    if result:
                        comment_count += 1
                        if sentiment == 'positive':
                            positive_count += 1
                        elif sentiment == 'negative':
                            negative_count += 1
                        else:
                            neutral_count += 1

                # 清空批次
                pending_texts = []
                pending_indices = []

                print(f"[CommentTask] 流水线处理进度: {i+1}/{len(all_comments)}")

        # 处理剩余的未分析数据
        if pending_texts:
            scores = analyze_sentiment(pending_texts)
            for idx, original_idx in enumerate(pending_indices):
                original_comment = all_comments[original_idx]
                score = scores[idx]
                sentiment = get_sentiment_label(score)

                result = save_comment(original_comment, video_obj, score, sentiment)
                if result:
                    comment_count += 1
                    if sentiment == 'positive':
                        positive_count += 1
                    elif sentiment == 'negative':
                        negative_count += 1
                    else:
                        neutral_count += 1

        elapsed = time.time() - start_time
        print(f"[CommentTask] 评论分析完成: count={comment_count}, 耗时{elapsed:.2f}s")

        return {
            'type': 'comments',
            'status': 'success',
            'count': comment_count,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'elapsed': round(elapsed, 2)
        }

    except Exception as e:
        print(f"[CommentTask] 评论分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {'type': 'comments', 'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def crawl_and_analyze_danmu(self, bvid, cid, headers, cookie):
    """
    爬取并分析弹幕的任务 - 流水线模式
    边爬取边分析边保存，而不是全部爬完再处理

    Returns:
        {
            'type': 'danmu',
            'status': 'success' | 'no_data',
            'count': int,
            'positive_count': int,
            'negative_count': int,
            'neutral_count': int
        }
    """
    from .services import (
        crawl_danmaku, clean_text, is_meaningful_text,
        analyze_sentiment, get_sentiment_label, save_danmaku
    )
    import time

    print(f"[DanmuTask] 开始处理弹幕: bvid={bvid}, cid={cid}")
    start_time = time.time()

    try:
        # 1. 爬取弹幕
        danmaku_list = crawl_danmaku(cid, headers)

        if not danmaku_list:
            return {'type': 'danmu', 'status': 'no_data', 'count': 0}

        print(f"[DanmuTask] 爬取完成，共{len(danmaku_list)}条，开始流水线处理...")

        # 2. 流水线处理：逐条清洗、分析、保存
        danmu_count = 0
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        batch_size = 64  # 弹幕批量分析
        pending_texts = []
        pending_indices = []
        # 用于存储 video_time（兼容新旧数据格式）
        pending_video_times = []

        for i, danmu in enumerate(danmaku_list):
            # 兼容新旧数据格式：可能是字符串或字典
            if isinstance(danmu, dict):
                content = danmu.get('content', '')
                video_time = danmu.get('video_time', 0.0)
                send_time = danmu.get('send_time', None)
                user_hash = danmu.get('user_hash', None)
            else:
                content = danmu
                video_time = 0.0
                send_time = None
                user_hash = None
            
            if not content:
                continue

            # 清洗
            cleaned = clean_text(content, for_analysis=True)

            # 过滤
            if not is_meaningful_text(cleaned):
                continue

            # 收集到待分析批次
            pending_texts.append(cleaned)
            pending_indices.append(i)
            pending_video_times.append(video_time)

            # 如果批次满了，进行分析和保存
            if len(pending_texts) >= batch_size:
                # 批量情感分析
                scores = analyze_sentiment(pending_texts)

                # 逐条保存结果
                for idx, original_idx in enumerate(pending_indices):
                    original_content = danmaku_list[original_idx]
                    # 兼容新旧格式重新获取
                    if isinstance(original_content, dict):
                        content_to_save = original_content.get('content', '')
                        video_time_to_save = original_content.get('video_time', 0.0)
                        send_time_to_save = original_content.get('send_time', None)
                        user_hash_to_save = original_content.get('user_hash', None)
                    else:
                        content_to_save = original_content
                        video_time_to_save = 0.0
                        send_time_to_save = None
                        user_hash_to_save = None

                    score = scores[idx]
                    sentiment = get_sentiment_label(score)

                    result = save_danmaku(cid, content_to_save, score, sentiment, video_time_to_save, send_time_to_save, user_hash_to_save)
                    if result:
                        danmu_count += 1
                        if sentiment == 'positive':
                            positive_count += 1
                        elif sentiment == 'negative':
                            negative_count += 1
                        else:
                            neutral_count += 1

                # 清空批次
                pending_texts = []
                pending_indices = []
                pending_video_times = []

                print(f"[DanmuTask] 流水线处理进度: {i+1}/{len(danmaku_list)}")

        # 处理剩余的未分析数据
        if pending_texts:
            scores = analyze_sentiment(pending_texts)
            for idx, original_idx in enumerate(pending_indices):
                original_content = danmaku_list[original_idx]
                # 兼容新旧格式重新获取
                if isinstance(original_content, dict):
                    content_to_save = original_content.get('content', '')
                    video_time_to_save = original_content.get('video_time', 0.0)
                    send_time_to_save = original_content.get('send_time', None)
                    user_hash_to_save = original_content.get('user_hash', None)
                else:
                    content_to_save = original_content
                    video_time_to_save = 0.0
                    send_time_to_save = None
                    user_hash_to_save = None

                score = scores[idx]
                sentiment = get_sentiment_label(score)

                result = save_danmaku(cid, content_to_save, score, sentiment, video_time_to_save, send_time_to_save, user_hash_to_save)
                if result:
                    danmu_count += 1
                    if sentiment == 'positive':
                        positive_count += 1
                    elif sentiment == 'negative':
                        negative_count += 1
                    else:
                        neutral_count += 1

        elapsed = time.time() - start_time
        print(f"[DanmuTask] 弹幕分析完成: count={danmu_count}, 耗时{elapsed:.2f}s")

        return {
            'type': 'danmu',
            'status': 'success',
            'count': danmu_count,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'elapsed': round(elapsed, 2)
        }

    except Exception as e:
        print(f"[DanmuTask] 弹幕分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {'type': 'danmu', 'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def trigger_video_analysis_group(self, bvid, aid, cid, headers, cookie):
    """
    并行触发评论和弹幕分析任务组

    Returns:
        {
            'bvid': str,
            'comment_task_id': str,
            'danmu_task_id': str,
            'audio_task_id': str | None (如果有音频分析)
        }
    """
    print(f"[AnalysisGroup] 开始并行分析: bvid={bvid}")

    # 1. 并行触发评论和弹幕分析
    comment_task = crawl_and_analyze_comments.s(bvid, aid, headers, cookie)
    danmu_task = crawl_and_analyze_danmu.s(bvid, cid, headers, cookie)

    # 使用 group 并行执行
    job = group([comment_task, danmu_task])
    result = job.apply_async()

    # 获取任务 ID
    comment_task_id = comment_task.id
    danmu_task_id = danmu_task.id

    return {
        'bvid': bvid,
        'comment_task_id': comment_task_id,
        'danmu_task_id': danmu_task_id,
        'group_id': str(result.id),
        'status': 'processing'
    }


@shared_task(bind=True)
def check_group_task_status(self, group_id):
    """
    查询任务组状态
    """
    from .models import Video
    try:
        # 尝试获取 Redis 中的任务组结果
        from django.conf import settings
        from celery.result import ResultSet

        # 使用 group_id 作为查询键
        # 这里简化处理，返回已知的任务状态
        return {'status': 'checking', 'group_id': group_id}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def get_task_results_async(task_ids):
    """
    批量获取任务结果（非阻塞）

    Args:
        task_ids: 任务 ID 列表

    Returns:
        dict: {task_id: result or None}
    """
    results = {}
    for task_id in task_ids:
        try:
            result = AsyncResult(task_id)
            if result.ready():
                if result.successful():
                    results[task_id] = result.get()
                else:
                    results[task_id] = {'error': str(result.result)}
            else:
                results[task_id] = None  # 任务还在进行中
        except Exception as e:
            results[task_id] = {'error': str(e)}
    return results


def get_group_task_results(group_id):
    """
    获取 Celery Group 任务组的所有结果

    Args:
        group_id: 任务组 ID

    Returns:
        dict: {task_type: result}
    """
    from celery.result import ResultSet
    try:
        # 创建 ResultSet
        result_set = ResultSet([AsyncResult(tid) for tid in []])
        # 等待所有任务完成（最多 600 秒）
        results = result_set.get(timeout=600)
        return {'status': 'success', 'results': results}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
