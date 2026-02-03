# 音频情感分析模型目录

## 说明

此目录用于存放 ONNX 格式的音频情感分析模型。

## 导出步骤

1. **安装依赖**：
```bash
cd D:\code\python\bilibili_analysis
pip install -r requirements.txt

# 安装 SpeechEmotionRecognition-Pytorch 依赖
cd D:\code\python\SpeechEmotionRecognition-Pytorch
pip install -r requirements.txt
```

2. **导出 ONNX 模型**：
```bash
cd D:\code\python\bilibili_analysis
python scripts/export_audio_onnx.py
```

3. **验证导出**：
导出完成后，此目录应包含：
- `audio_emotion_model.onnx` - ONNX 模型文件
- `audio_label_list.txt` - 情感标签列表
- `audio_scaler.pkl` - 特征归一化器

## 使用方法

```python
from analysis.audio_sentiment_model import AudioSentimentModel

# 初始化模型
model = AudioSentimentModel()

# 预测单个音频
emotion, score = model.predict("path/to/audio.wav")

# 批量预测
results = model.predict_batch(["audio1.wav", "audio2.wav"])

# 获取所有类别概率
probs = model.get_all_probabilities("audio.wav")
```

## 模型信息

- **基础模型**: BiLSTM + Emotion2Vec
- **训练数据**: SpeechEmotionRecognition-Pytorch/dataset/
- **类别**: angry, fearful, happy, neutral, sad, surprise
- **特征维度**: 768
