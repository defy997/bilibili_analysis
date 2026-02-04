from django.db import models

# Create your models here.

class Video(models.Model):
    bvid = models.CharField(max_length=20, primary_key=True, verbose_name="视频BV号")
    aid = models.BigIntegerField(unique=True, verbose_name="视频AV号")
    cid = models.BigIntegerField(null=True, verbose_name="弹幕ID")
    title = models.CharField(max_length=255, null=True, verbose_name="视频标题")
    pubdate = models.DateTimeField(null=True, verbose_name="发布日期")
    raw_comment_count = models.IntegerField(default=0, verbose_name="原始爬取评论数")

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
    reply_count = models.IntegerField(default=0, verbose_name="回复数/子评论数")
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


class AudioSentiment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='audio_sentiments')
    time_offset = models.FloatField(verbose_name="视频内时间偏移(秒)")
    sentiment_score = models.FloatField(default=0.5, verbose_name="情感得分")
    sentiment_label = models.CharField(max_length=10, default="neutral")
    emotion_probs = models.JSONField(default=dict, verbose_name="各情感概率分布")
    segment_duration = models.FloatField(default=15, verbose_name="分段时长(秒)")
    text_transcript = models.TextField(null=True, blank=True, verbose_name="ASR转录文本")

    class Meta:
        db_table = 'audio_sentiments'
        ordering = ['time_offset']

    def __str__(self):
        return f"AudioSentiment({self.video_id}, t={self.time_offset}s)"


class UserConfig(models.Model):
    """用户配置表（单例模式，只有一条记录）"""
    # 数据过滤配置
    min_length = models.IntegerField(default=1, verbose_name="最小文本长度")
    max_length = models.IntegerField(default=500, verbose_name="最大文本长度")
    min_chinese_ratio = models.FloatField(default=0.15, verbose_name="最小中文占比")
    min_quality_score = models.FloatField(default=0.2, verbose_name="最小质量评分")

    # 去重配置
    dedup_method = models.CharField(max_length=20, default='exact', verbose_name="去重方法")
    fuzzy_threshold = models.FloatField(default=0.85, verbose_name="模糊去重阈值")
    embedding_threshold = models.FloatField(default=0.85, verbose_name="语义去重阈值")

    # 垃圾检测配置
    max_char_repeat = models.IntegerField(default=10, verbose_name="单字符最大重复")
    min_unique_ratio = models.FloatField(default=0.2, verbose_name="最小字符多样性")
    min_unique_check_length = models.IntegerField(default=15, verbose_name="多样性检查长度")

    # 白名单配置
    high_like_threshold = models.IntegerField(default=50, verbose_name="高赞阈值")
    high_reply_threshold = models.IntegerField(default=10, verbose_name="热门讨论阈值")
    combined_like_threshold = models.IntegerField(default=20, verbose_name="综合热度-点赞")
    combined_reply_threshold = models.IntegerField(default=5, verbose_name="综合热度-回复")

    # UI配置
    background_color = models.CharField(max_length=7, default="#1a1a2e", verbose_name="背景颜色")
    opacity = models.FloatField(default=0.95, verbose_name="透明度")

    # 元数据
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'user_config'
        verbose_name = "用户配置"
        verbose_name_plural = "用户配置"

    def __str__(self):
        return f"配置 (更新于 {self.updated_at})"

    @classmethod
    def get_config(cls):
        """获取配置（单例模式）"""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def to_dict(self):
        """转换为字典"""
        return {
            'filter_config': {
                'min_length': self.min_length,
                'max_length': self.max_length,
                'min_chinese_ratio': self.min_chinese_ratio,
                'min_quality_score': self.min_quality_score,
                'dedup_method': self.dedup_method,
                'fuzzy_threshold': self.fuzzy_threshold,
                'embedding_threshold': self.embedding_threshold,
                'max_char_repeat': self.max_char_repeat,
                'min_unique_ratio': self.min_unique_ratio,
                'min_unique_check_length': self.min_unique_check_length,
            },
            'whitelist_config': {
                'high_like_threshold': self.high_like_threshold,
                'high_reply_threshold': self.high_reply_threshold,
                'combined_like_threshold': self.combined_like_threshold,
                'combined_reply_threshold': self.combined_reply_threshold,
            },
            'ui_config': {
                'background_color': self.background_color,
                'opacity': self.opacity,
            }
        }


class User(models.Model):
    """用户模型"""
    username = models.CharField(max_length=50, unique=True, verbose_name="用户名")
    email = models.EmailField(unique=True, verbose_name="邮箱")
    password = models.CharField(max_length=255, verbose_name="密码(哈希)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="注册时间")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    last_login = models.DateTimeField(null=True, blank=True, verbose_name="最后登录时间")

    # === 用户个人配置 ===
    # 数据过滤配置
    min_length = models.IntegerField(default=1, verbose_name="最小文本长度")
    max_length = models.IntegerField(default=500, verbose_name="最大文本长度")
    min_chinese_ratio = models.FloatField(default=0.15, verbose_name="最小中文占比")
    min_quality_score = models.FloatField(default=0.2, verbose_name="最小质量评分")

    # 去重配置
    dedup_method = models.CharField(max_length=20, default='exact', verbose_name="去重方法")
    fuzzy_threshold = models.FloatField(default=0.85, verbose_name="模糊去重阈值")
    embedding_threshold = models.FloatField(default=0.85, verbose_name="语义去重阈值")

    # 垃圾检测配置
    max_char_repeat = models.IntegerField(default=10, verbose_name="单字符最大重复")
    min_unique_ratio = models.FloatField(default=0.2, verbose_name="最小字符多样性")
    min_unique_check_length = models.IntegerField(default=15, verbose_name="多样性检查长度")

    # 白名单配置
    high_like_threshold = models.IntegerField(default=50, verbose_name="高赞阈值")
    high_reply_threshold = models.IntegerField(default=10, verbose_name="热门讨论阈值")
    combined_like_threshold = models.IntegerField(default=20, verbose_name="综合热度-点赞")
    combined_reply_threshold = models.IntegerField(default=5, verbose_name="综合热度-回复")

    # UI配置
    background_color = models.CharField(max_length=7, default="#1a1a2e", verbose_name="背景颜色")
    opacity = models.FloatField(default=0.95, verbose_name="透明度")

    class Meta:
        db_table = 'users'
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username

    def get_config(self):
        """获取用户配置"""
        return {
            'filter_config': {
                'min_length': self.min_length,
                'max_length': self.max_length,
                'min_chinese_ratio': self.min_chinese_ratio,
                'min_quality_score': self.min_quality_score,
                'dedup_method': self.dedup_method,
                'fuzzy_threshold': self.fuzzy_threshold,
                'embedding_threshold': self.embedding_threshold,
                'max_char_repeat': self.max_char_repeat,
                'min_unique_ratio': self.min_unique_ratio,
                'min_unique_check_length': self.min_unique_check_length,
            },
            'whitelist_config': {
                'high_like_threshold': self.high_like_threshold,
                'high_reply_threshold': self.high_reply_threshold,
                'combined_like_threshold': self.combined_like_threshold,
                'combined_reply_threshold': self.combined_reply_threshold,
            },
            'ui_config': {
                'background_color': self.background_color,
                'opacity': self.opacity,
            }
        }


class EmailVerificationCode(models.Model):
    """邮箱验证码模型"""
    email = models.EmailField(verbose_name="邮箱")
    code = models.CharField(max_length=6, verbose_name="验证码")
    purpose = models.CharField(max_length=20, default='register', verbose_name="用途")  # register, reset_password
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    expires_at = models.DateTimeField(verbose_name="过期时间")
    is_used = models.BooleanField(default=False, verbose_name="是否已使用")

    class Meta:
        db_table = 'email_verification_codes'
        verbose_name = "邮箱验证码"
        verbose_name_plural = "邮箱验证码"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} - {self.code}"

    def is_valid(self):
        """检查验证码是否有效"""
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at