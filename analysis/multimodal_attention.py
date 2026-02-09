"""
多模态情感分析 - 注意力机制融合
支持音频、文本、弹幕的情感融合
纯 Python 实现，无需 PyTorch
"""


def simple_attention_fusion(audio_score, text_score, danmu_score,
                            audio_conf=1.0, text_conf=1.0, danmu_conf=1.0):
    """
    简化版注意力融合（无需训练，基于置信度）
    适合快速部署

    Args:
        audio_score: 音频情感得分 dict {"positive": 0.7, "neutral": 0.2, "negative": 0.1}
        text_score: 文本情感得分 dict
        danmu_score: 弹幕情感得分 dict
        audio_conf: 音频置信度 [0-1]
        text_conf: 文本置信度 [0-1]
        danmu_conf: 弹幕置信度 [0-1]

    Returns:
        融合情感得分 dict
        注意力权重 dict
    """
    # 基于置信度计算注意力权重（归一化）
    total_conf = audio_conf + text_conf + danmu_conf
    weights = {
        'audio': audio_conf / total_conf,
        'text': text_conf / total_conf,
        'danmu': danmu_conf / total_conf
    }

    # 加权融合
    fused_scores = {}
    for emotion in ['positive', 'neutral', 'negative']:
        fused_scores[emotion] = (
            weights['audio'] * audio_score.get(emotion, 0) +
            weights['text'] * text_score.get(emotion, 0) +
            weights['danmu'] * danmu_score.get(emotion, 0)
        )

    return fused_scores, weights


def adaptive_attention_fusion(audio_score, text_score, danmu_score, video_type='general'):
    """
    自适应注意力融合
    根据视频类型自动调整权重

    Args:
        audio_score: 音频情感得分
        text_score: 文本情感得分
        danmu_score: 弹幕情感得分
        video_type: 视频类型 ('music', 'tutorial', 'vlog', 'game', 'general')

    Returns:
        融合情感得分 dict
        注意力权重 dict
    """
    # 预设不同视频类型的模态权重
    type_weights = {
        'music': {'audio': 0.6, 'text': 0.2, 'danmu': 0.2},     # 音乐视频：音频最重要
        'tutorial': {'audio': 0.2, 'text': 0.5, 'danmu': 0.3},   # 教程：文本最重要
        'vlog': {'audio': 0.4, 'text': 0.4, 'danmu': 0.2},       # Vlog：音频和文本均衡
        'game': {'audio': 0.3, 'text': 0.3, 'danmu': 0.4},       # 游戏：弹幕重要
        'general': {'audio': 0.35, 'text': 0.35, 'danmu': 0.3}   # 通用：相对均衡
    }

    # 获取权重
    weights = type_weights.get(video_type, type_weights['general'])

    # 基于情感强度动态调整（如果某个模态情感非常明确，增加其权重）
    audio_strength = max(audio_score.values()) - min(audio_score.values())
    text_strength = max(text_score.values()) - min(text_score.values())
    danmu_strength = max(danmu_score.values()) - min(danmu_score.values())

    # 强度加成（情感越明确，权重越高）
    strength_bonus = {
        'audio': audio_strength * 0.1,
        'text': text_strength * 0.1,
        'danmu': danmu_strength * 0.1
    }

    # 应用强度加成并归一化
    adjusted_weights = {
        k: v + strength_bonus[k] for k, v in weights.items()
    }
    total = sum(adjusted_weights.values())
    adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}

    # 加权融合
    fused_scores = {}
    for emotion in ['positive', 'neutral', 'negative']:
        fused_scores[emotion] = (
            adjusted_weights['audio'] * audio_score.get(emotion, 0) +
            adjusted_weights['text'] * text_score.get(emotion, 0) +
            adjusted_weights['danmu'] * danmu_score.get(emotion, 0)
        )

    return fused_scores, adjusted_weights


def detect_emotion_conflict(audio_score, text_score, danmu_score, threshold=0.4):
    """
    检测情感冲突
    识别不同模态情感不一致的情况

    Args:
        audio_score: 音频情感得分
        text_score: 文本情感得分
        danmu_score: 弹幕情感得分
        threshold: 冲突阈值

    Returns:
        冲突信息 dict
    """
    # 获取各模态的主导情感
    audio_dominant = max(audio_score, key=audio_score.get)
    text_dominant = max(text_score, key=text_score.get)
    danmu_dominant = max(danmu_score, key=danmu_score.get)

    conflicts = []

    # 检测音频-文本冲突
    if audio_dominant != text_dominant:
        audio_conf = audio_score[audio_dominant]
        text_conf = text_score[text_dominant]
        if audio_conf > threshold and text_conf > threshold:
            conflicts.append({
                'type': 'audio-text',
                'audio_emotion': audio_dominant,
                'text_emotion': text_dominant,
                'severity': abs(audio_conf - text_conf),
                'interpretation': '可能存在讽刺或情感表达不一致'
            })

    # 检测文本-弹幕冲突
    if text_dominant != danmu_dominant:
        text_conf = text_score[text_dominant]
        danmu_conf = danmu_score[danmu_dominant]
        if text_conf > threshold and danmu_conf > threshold:
            conflicts.append({
                'type': 'text-danmu',
                'text_emotion': text_dominant,
                'danmu_emotion': danmu_dominant,
                'severity': abs(text_conf - danmu_conf),
                'interpretation': '用户反馈与评论内容情感不一致'
            })

    return {
        'has_conflict': len(conflicts) > 0,
        'conflicts': conflicts,
        'consistency_score': 1.0 - (len(conflicts) * 0.3)  # 一致性得分
    }


# ============= 示例用法 =============
if __name__ == '__main__':
    # 示例：简单融合
    audio = {'positive': 0.8, 'neutral': 0.15, 'negative': 0.05}
    text = {'positive': 0.6, 'neutral': 0.3, 'negative': 0.1}
    danmu = {'positive': 0.7, 'neutral': 0.2, 'negative': 0.1}

    # 方法1：基于置信度的简单融合
    fused, weights = simple_attention_fusion(audio, text, danmu)
    print("简单融合结果:", fused)
    print("注意力权重:", weights)

    # 方法2：自适应融合（音乐视频）
    fused2, weights2 = adaptive_attention_fusion(audio, text, danmu, video_type='music')
    print("\n音乐视频自适应融合:", fused2)
    print("自适应权重:", weights2)

    # 方法3：冲突检测
    audio_conflict = {'positive': 0.1, 'neutral': 0.2, 'negative': 0.7}  # 负面
    text_conflict = {'positive': 0.8, 'neutral': 0.15, 'negative': 0.05}  # 正面
    conflict_info = detect_emotion_conflict(audio_conflict, text_conflict, danmu)
    print("\n冲突检测:", conflict_info)
