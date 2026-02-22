"""
添加 Comment 和 Danmu 表的复合索引

- Comment 表: (video_id, sentiment_label, ctime)
- Danmu 表: (cid, sentiment_label, send_time)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0018_add_user_video_history'),
    ]

    operations = [
        # Comment 表添加复合索引
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['video', 'sentiment_label', 'ctime'],
                name='comment_video_sentiment_idx'
            ),
        ),
        
        # Danmu 表添加复合索引
        migrations.AddIndex(
            model_name='danmu',
            index=models.Index(
                fields=['cid', 'sentiment_label', 'send_time'],
                name='danmu_cid_sentiment_idx'
            ),
        ),
        
        # Comment 表添加 ctime 索引（如果还没有）
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(
                fields=['ctime'],
                name='comment_ctime_idx'
            ),
        ),
        
        # Danmu 表添加 send_time 索引（如果还没有）
        migrations.AddIndex(
            model_name='danmu',
            index=models.Index(
                fields=['send_time'],
                name='danmu_send_time_idx'
            ),
        ),
    ]
