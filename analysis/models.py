from django.db import models

# Create your models here.

class Video(models.Model):
    bvid = models.CharField(max_length=20, primary_key=True, verbose_name="视频BV号")
    aid = models.BigIntegerField(unique=True, verbose_name="视频AV号")
    cid = models.BigIntegerField(null=True, verbose_name="弹幕ID")
    title = models.CharField(max_length=255, null=True, verbose_name="视频标题")
    pubdate = models.DateTimeField(null=True, verbose_name="发布日期")

    class Meta:
        db_table = 'videos'
        ordering = ['-pubdate']

    def __str__(self):
        return self.title

class Comment(models.Model):
    rpid = models.BigIntegerField(primary_key=True, verbose_name="评论ID")
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='comments', verbose_name="视频")

    # 用户信息
    mid = models.BigIntegerField(verbose_name="用户UID")
    uname = models.CharField(max_length=100, null=True, verbose_name="用户名")

    # 评论内容
    message = models.TextField(verbose_name="评论正文")
    like_count = models.IntegerField(default=0, verbose_name="点赞数")
    location = models.CharField(max_length=50, null=True, verbose_name="IP属地")
    ctime = models.DateTimeField(null=True, verbose_name="发布时间")

    # 扩展字段
    vip_type = models.IntegerField(default=0, verbose_name="会员类型")
    vip_label = models.CharField(max_length=50, null=True, verbose_name="会员标签")
    user_level = models.IntegerField(default=0, verbose_name="用户等级")

    parent_rpid = models.BigIntegerField(default=0, verbose_name="父评论ID")

    # 情感分析字段
    sentiment_score = models.FloatField(default=0.5, verbose_name="情感得分")
    sentiment_label = models.CharField(max_length=10, default="neutral", verbose_name="情感分类")

    # 数据清洗字段（阶段二、三新增）
    quality_score = models.FloatField(default=0.5, verbose_name="质量评分")
    is_duplicate = models.BooleanField(default=False, verbose_name="是否重复")
    duplicate_group = models.CharField(max_length=100, null=True, blank=True, verbose_name="重复组ID")

    class Meta:
        db_table = 'comments'
        ordering = ['-ctime']

    def __str__(self):
        return f"Comment {self.rpid}"

class Danmu(models.Model):
    # 注意：SQL中 videos.cid 不是主键或唯一键，因此Django无法直接创建ForeignKey
    # 这里使用 BigIntegerField 并建立索引，与SQL定义一致
    cid = models.BigIntegerField(db_index=True, verbose_name="关联视频CID")

    video_time = models.FloatField(default=0, verbose_name="视频内出现时间")
    content = models.TextField(verbose_name="弹幕内容")
    send_time = models.DateTimeField(null=True, verbose_name="真实发送时间")
    user_hash = models.CharField(max_length=20, null=True, verbose_name="发送者Hash值")

    # 情感分析字段
    sentiment_score = models.FloatField(default=0.5, verbose_name="情感得分")
    sentiment_label = models.CharField(max_length=10, default="neutral", verbose_name="情感分类")

    # 数据清洗字段（阶段二、三新增）
    quality_score = models.FloatField(default=0.5, verbose_name="质量评分")
    is_duplicate = models.BooleanField(default=False, verbose_name="是否重复")
    duplicate_group = models.CharField(max_length=100, null=True, blank=True, verbose_name="重复组ID")

    class Meta:
        db_table = 'danmus'
        ordering = ['-send_time']

    def __str__(self):
        return self.content[:20]