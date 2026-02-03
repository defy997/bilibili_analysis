"""
音频情感分析集成示例

用法：
    from analysis.audio_sentiment_model import AudioSentimentModel

    # 初始化模型（只需一次）
    model = AudioSentimentModel()

    # 预测单个音频
    label, score = model.predict("path/to/audio.wav")

    # 批量预测
    results = model.predict_batch([
        "audio1.wav",
        "audio2.wav",
        "audio3.wav"
    ])

    # 获取所有类别概率
    probs = model.get_all_probabilities("audio.wav")
"""

import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from analysis.audio_sentiment_model import AudioSentimentModel


def test_single_prediction():
    """测试单个音频预测"""
    model = AudioSentimentModel()
    
    # 测试音频
    test_audio = os.path.join(
        PROJECT_ROOT,
        "SpeechEmotionRecognition-Pytorch",
        "dataset",
        "test.wav"
    )
    
    if not os.path.exists(test_audio):
        print(f"测试音频不存在: {test_audio}")
        return
    
    # 预测
    label, score = model.predict(test_audio)
    
    print("=" * 50)
    print("音频情感分析结果")
    print("=" * 50)
    print(f"音频文件: {test_audio}")
    print(f"预测情感: {label}")
    print(f"置信度: {score:.4f}")
    print()
    
    # 所有类别概率
    probs = model.get_all_probabilities(test_audio)
    print("各类别概率:")
    for emotion, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(prob * 30)
        print(f"  {emotion:10s}: {prob:.4f} {bar}")


def test_batch_prediction():
    """测试批量预测"""
    model = AudioSentimentModel()
    
    # 模拟音频列表
    audio_paths = [
        "path/to/audio1.wav",
        "path/to/audio2.wav",
        "path/to/audio3.wav",
    ]
    
    # 实际测试使用存在的音频
    test_dir = os.path.join(
        PROJECT_ROOT,
        "SpeechEmotionRecognition-Pytorch",
        "dataset"
    )
    audio_paths = [
        os.path.join(test_dir, f)
        for f in os.listdir(test_dir)
        if f.endswith('.wav')
    ][:5]  # 只测试前5个
    
    print("=" * 50)
    print(f"批量预测测试 ({len(audio_paths)} 个音频)")
    print("=" * 50)
    
    results = model.predict_batch(audio_paths)
    
    for path, (label, score) in zip(audio_paths, results):
        print(f"{os.path.basename(path):30s} -> {label:10s} ({score:.4f})")


def integrate_with_django():
    """
    在 Django 项目中集成的示例

    在 views.py 或 tasks.py 中使用：

    from analysis.audio_sentiment_model import AudioSentimentModel

    def analyze_video_audio(video_id):
        '''分析视频的音频情感'''
        model = AudioSentimentModel()

        # 获取视频的音频文件
        audio_path = get_video_audio_path(video_id)

        # 分析
        emotion, score = model.predict(audio_path)

        # 保存结果到数据库
        VideoAudioSentiment.objects.create(
            video_id=video_id,
            emotion=emotion,
            confidence=score
        )

        return emotion, score
    """
    pass


if __name__ == "__main__":
    print("音频情感分析集成测试")
    print("=" * 50)
    
    # 单个预测测试
    test_single_prediction()
    
    print("\n")
    
    # 批量预测测试
    test_batch_prediction()
