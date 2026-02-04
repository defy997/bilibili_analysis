"""
音频情感分析模型 - 使用 ONNX 格式的 BiLSTM 模型

支持功能：
1. ONNX 模型加载和推理
2. 音频特征提取（MFCC + 多种音频特征）
3. 批量预测

使用方法：
    model = AudioSentimentModel()
    emotion, score = model.predict(audio_path)
    results = model.predict_batch([audio_path1, audio_path2])
"""
import gc
import os
import pickle
from typing import List, Tuple, Union

import librosa
import numpy as np
import onnxruntime as ort


class AudioSentimentModel:
    """音频情感分析模型类（ONNX 格式）"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AudioSentimentModel, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, model_path=None):
        if hasattr(self, 'initialized') and self.initialized:
            return
        
        # 默认模型路径
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__),
                "..", "models", "audio_emotion", "audio_emotion_model.onnx"
            )
        
        self.model_path = model_path
        model_dir = os.path.dirname(model_path)
        
        print(f"正在加载音频情感模型: {model_path}")
        
        # 加载 ONNX 模型（优化线程和图优化等级）
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 2
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(model_path, sess_options)
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]
        
        # 加载标签列表
        label_path = os.path.join(model_dir, "audio_label_list.txt")
        if os.path.exists(label_path):
            with open(label_path, 'r', encoding='utf-8') as f:
                self.class_labels = [l.strip() for l in f.readlines() if l.strip()]
        else:
            # 默认标签（根据你的训练数据）
            self.class_labels = ['angry', 'fearful', 'happy', 'neutral', 'sad', 'surprise']
        
        # 加载归一化器 (使用 joblib 加载，因为 scaler 是用 joblib.dump 保存的)
        scaler_path = os.path.join(model_dir, "audio_scaler.pkl")
        if os.path.exists(scaler_path):
            try:
                import joblib
                with open(scaler_path, 'rb') as f:
                    self.scaler = joblib.load(f)
                self.has_scaler = True
            except Exception as e:
                print(f"[Warning] 加载 scaler 失败，跳过归一化: {e}")
                self.scaler = None
                self.has_scaler = False
        else:
            self.scaler = None
            self.has_scaler = False
        
        self.feature_dim = 768  # Emotion2Vec 特征维度
        self.initialized = True
        print(f"音频情感模型加载完成！类别: {self.class_labels}")
    
    def extract_features(self, audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        提取音频特征（Emotion2Vec 风格）
        
        :param audio_data: 音频数据 (numpy array)
        :param sample_rate: 采样率
        :return: 特征向量
        """
        # 使用 librosa 提取 MFCC 特征
        # MFCC 特征是语音情感分析的常用特征
        
        # 4. 梅尔频谱特征（先计算，复用于 MFCC）
        mel_spec = librosa.feature.melspectrogram(y=audio_data, sr=sample_rate, n_mels=128)
        log_mel = librosa.power_to_db(mel_spec, ref=np.max)

        # 1. 提取 MFCC 特征 (13 维)，复用 log_mel
        mfccs = librosa.feature.mfcc(S=log_mel, sr=sample_rate, n_mfcc=13)
        mfccs_mean = np.mean(mfccs, axis=1)
        mfccs_std = np.std(mfccs, axis=1)

        # 2. 提取 Delta MFCC
        delta_mfccs = librosa.feature.delta(mfccs)
        delta_mean = np.mean(delta_mfccs, axis=1)
        delta_std = np.std(delta_mfccs, axis=1)

        # 3. 提取 Delta2 MFCC
        delta2_mfccs = librosa.feature.delta(mfccs, order=2)
        delta2_mean = np.mean(delta2_mfccs, axis=1)
        delta2_std = np.std(delta2_mfccs, axis=1)
        mel_spec_mean = np.mean(mel_spec, axis=1)
        mel_spec_std = np.std(mel_spec, axis=1)
        mel_spec_max = np.max(mel_spec, axis=1)
        
        # 5. 频谱特征
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_data, sr=sample_rate)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)
        spectral_contrast = librosa.feature.spectral_contrast(y=audio_data, sr=sample_rate)
        spectral_flatness = librosa.feature.spectral_flatness(y=audio_data)
        
        # 6. 过零率
        zero_crossing_rate = librosa.feature.zero_crossing_rate(audio_data)
        
        # 7. 能量相关
        rms = librosa.feature.rms(y=audio_data)
        
        # 8. 音高相关（如果音频足够长）
        try:
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=sample_rate)
            pitch_mean = np.mean(pitches[magnitudes > np.percentile(magnitudes, 50)])
            pitch_std = np.std(pitches[magnitudes > np.percentile(magnitudes, 50)])
        except:
            pitch_mean = 0
            pitch_std = 0
        
        # 9. 色度特征
        chroma = librosa.feature.chroma_stft(y=audio_data, sr=sample_rate)
        chroma_mean = np.mean(chroma, axis=1)
        
        # 拼接所有特征 - 确保所有值都是1D数组，避免0维数组导致的concatenate错误
        features = np.concatenate([
            # MFCC 及其 delta (13*3 = 39)
            np.atleast_1d(mfccs_mean), np.atleast_1d(mfccs_std),
            np.atleast_1d(delta_mean), np.atleast_1d(delta_std),
            np.atleast_1d(delta2_mean), np.atleast_1d(delta2_std),
            # 梅尔频谱 (128*3 = 384)
            np.atleast_1d(mel_spec_mean), np.atleast_1d(mel_spec_std), np.atleast_1d(mel_spec_max),
            # 频谱特征 (1+1+1+7+1 = 11)
            np.atleast_1d(np.mean(spectral_centroid)), np.atleast_1d(np.std(spectral_centroid)),
            np.atleast_1d(np.mean(spectral_bandwidth)), np.atleast_1d(np.std(spectral_bandwidth)),
            np.atleast_1d(np.mean(spectral_rolloff)), np.atleast_1d(np.std(spectral_rolloff)),
            np.atleast_1d(np.mean(spectral_contrast, axis=1)),
            np.atleast_1d(np.mean(spectral_flatness)), np.atleast_1d(np.std(spectral_flatness)),
            # 过零率 (2)
            np.atleast_1d(np.mean(zero_crossing_rate)), np.atleast_1d(np.std(zero_crossing_rate)),
            # 能量 (2)
            np.atleast_1d(np.mean(rms)), np.atleast_1d(np.std(rms)),
            # 音高 (2)
            np.atleast_1d(pitch_mean), np.atleast_1d(pitch_std),
            # 色度 (12)
            np.atleast_1d(chroma_mean),
        ])
        
        # 填充或截断到固定维度
        if len(features) < self.feature_dim:
            features = np.pad(features, (0, self.feature_dim - len(features)))
        else:
            features = features[:self.feature_dim]
        
        return features.astype(np.float32)
    
    def preprocess_audio(self, audio_path: str) -> np.ndarray:
        """
        预处理音频文件
        
        :param audio_path: 音频文件路径
        :return: 预处理后的特征
        """
        # 加载音频
        audio_data, sample_rate = librosa.load(audio_path, sr=16000)
        
        # 跳过太短的音频
        if len(audio_data) < 1600:  # 少于 0.1 秒
            return None
        
        # 提取特征
        features = self.extract_features(audio_data, sample_rate)
        
        # 归一化
        if self.has_scaler and self.scaler is not None:
            features = self.scaler.transform([features])[0].astype(np.float32)
        
        return features
    
    def predict(
        self,
        audio_data: Union[str, np.ndarray],
        sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """
        预测单个音频的情感
        
        :param audio_data: 音频文件路径或音频数据 (numpy array)
        :param sample_rate: 采样率（当 audio_data 是 numpy 时需要）
        :return: (情感标签, 置信度分数)
        """
        # 预处理
        if isinstance(audio_data, str):
            features = self.preprocess_audio(audio_data)
        else:
            features = self.extract_features(audio_data, sample_rate)
            if self.has_scaler and self.scaler is not None:
                features = self.scaler.transform([features])[0].astype(np.float32)

        if features is None:
            return "neutral", 0.0
        
        # 推理
        features = np.expand_dims(features, axis=0)
        ort_inputs = {self.input_names[0]: features}
        logits = self.session.run(None, ort_inputs)[0]
        
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        # 获取最大概率的类别
        pred_idx = np.argmax(probs[0])
        pred_label = self.class_labels[pred_idx]
        pred_score = float(probs[0][pred_idx])
        
        return pred_label, pred_score
    
    def predict_batch(
        self,
        audio_paths: List[str],
        batch_size: int = 32
    ) -> List[Tuple[str, float]]:
        """
        批量预测多个音频的情感
        
        :param audio_paths: 音频文件路径列表
        :param batch_size: 批量大小
        :return: 预测结果列表 [(标签, 分数), ...]
        """
        results = []
        
        for i in range(0, len(audio_paths), batch_size):
            batch_paths = audio_paths[i:i + batch_size]
            
            # 预处理批量
            batch_features = []
            valid_indices = []
            
            for j, audio_path in enumerate(batch_paths):
                features = self.preprocess_audio(audio_path)
                if features is not None:
                    batch_features.append(features)
                    valid_indices.append(j)
            
            if not batch_features:
                # 所有音频都太短
                for j in range(len(batch_paths)):
                    results.append(("neutral", 0.0))
                continue
            
            # 堆叠为批量
            batch_array = np.array(batch_features, dtype=np.float32)
            
            # 推理
            ort_inputs = {self.input_names[0]: batch_array}
            logits = self.session.run(None, ort_inputs)[0]
            
            # Softmax
            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
            
            # 获取结果
            pred_indices = np.argmax(probs, axis=1)
            pred_scores = np.max(probs, axis=1)
            
            # 填充结果
            batch_results = [("neutral", 0.0)] * len(batch_paths)
            for k, idx in enumerate(valid_indices):
                batch_results[idx] = (
                    self.class_labels[pred_indices[k]],
                    float(pred_scores[k])
                )
            
            results.extend(batch_results)
        
        return results
    
    def get_all_probabilities(
        self,
        audio_data: Union[str, np.ndarray],
        sample_rate: int = 16000
    ) -> dict:
        """
        获取所有类别的概率分布
        
        :param audio_data: 音频文件路径或音频数据
        :param sample_rate: 采样率
        :return: {类别标签: 概率, ...}
        """
        # 预处理
        if isinstance(audio_data, str):
            features = self.preprocess_audio(audio_data)
        else:
            features = self.extract_features(audio_data, sample_rate)
            if self.has_scaler and self.scaler is not None:
                features = self.scaler.transform([features])[0].astype(np.float32)

        if features is None:
            return {label: 0.0 for label in self.class_labels}
        
        # 推理
        features = np.expand_dims(features, axis=0)
        ort_inputs = {self.input_names[0]: features}
        logits = self.session.run(None, ort_inputs)[0]
        
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        return {
            label: float(probs[0][i])
            for i, label in enumerate(self.class_labels)
        }


    # 情感标签 → 情感极性映射 (0=消极, 0.5=中性, 1=积极)
    EMOTION_POLARITY = {
        'happy': 0.85,
        'surprise': 0.70,
        'neutral': 0.50,
        'fearful': 0.25,
        'sad': 0.20,
        'angry': 0.15,
    }

    @staticmethod
    def emotion_to_polarity(probabilities: dict) -> float:
        """
        将情感概率分布转换为 0-1 情感极性分数

        加权求和：每个情感的概率 × 该情感对应的极性值
        """
        polarity = 0.0
        for label, prob in probabilities.items():
            polarity += prob * AudioSentimentModel.EMOTION_POLARITY.get(label, 0.5)
        return round(max(0.0, min(1.0, polarity)), 4)

    def analyze_segments(
        self,
        audio_path: str,
        sr: int = 16000,
        segment_duration: float = 15,
        overlap: float = 5,
    ) -> List[dict]:
        """
        将音频分段分析情感波动

        :param audio_path: 音频文件路径
        :param sr: 采样率
        :param segment_duration: 每段时长（秒）
        :param overlap: 重叠时长（秒）
        :return: [{time_offset, label, score, sentiment_score, probabilities, segment_duration}, ...]
            - score: 模型对 label 的置信度
            - sentiment_score: 0-1 情感极性（0=消极, 1=积极）
        """
        audio_data, _ = librosa.load(audio_path, sr=sr, mono=True)
        total_duration = len(audio_data) / sr

        # 短视频自动调整分段时长
        if total_duration < 30:
            segment_duration = max(5, total_duration / 3)
            overlap = segment_duration * 0.3

        step = segment_duration - overlap
        min_segment = 5.0  # 尾段最小保留长度（秒）
        results = []

        offset = 0.0
        while offset < total_duration:
            end = min(offset + segment_duration, total_duration)
            seg_len = end - offset

            # 尾段太短则丢弃
            if seg_len < min_segment and offset > 0:
                break

            start_sample = int(offset * sr)
            end_sample = int(end * sr)
            segment = audio_data[start_sample:end_sample]

            # 提取特征
            features = self.extract_features(segment, sr)
            if self.has_scaler and self.scaler is not None:
                features = self.scaler.transform([features])[0].astype(np.float32)

            # ONNX 推理
            features_input = np.expand_dims(features, axis=0)
            ort_inputs = {self.input_names[0]: features_input}
            logits = self.session.run(None, ort_inputs)[0]

            # Softmax
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / np.sum(exp_logits)

            pred_idx = np.argmax(probs[0])
            pred_label = self.class_labels[pred_idx]
            pred_score = float(probs[0][pred_idx])

            probabilities = {
                label: float(probs[0][i])
                for i, label in enumerate(self.class_labels)
            }

            sentiment_score = self.emotion_to_polarity(probabilities)

            results.append({
                'time_offset': round(offset, 2),
                'label': pred_label,
                'score': pred_score,
                'sentiment_score': sentiment_score,
                'probabilities': probabilities,
                'segment_duration': round(seg_len, 2),
            })

            # 释放中间变量
            del segment, features, features_input, logits, exp_logits, probs

            offset += step

        # 释放音频数据
        del audio_data
        gc.collect()

        return results


# 便捷函数
def analyze_audio_sentiment(audio_path: str) -> Tuple[str, float]:
    """分析单个音频的情感"""
    model = AudioSentimentModel()
    return model.predict(audio_path)


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        # 使用 SpeechEmotionRecognition-Pytorch 中的测试音频
        audio_path = os.path.join(
            os.path.dirname(__file__),
            "..", "SpeechEmotionRecognition-Pytorch", "dataset", "test.wav"
        )
    
    if not os.path.exists(audio_path):
        print(f"音频文件不存在: {audio_path}")
        sys.exit(1)
    
    model = AudioSentimentModel()
    
    # 单个预测
    label, score = model.predict(audio_path)
    print(f"\n单个预测结果:")
    print(f"  音频: {audio_path}")
    print(f"  情感: {label}")
    print(f"  分数: {score:.4f}")
    
    # 所有类别概率
    probs = model.get_all_probabilities(audio_path)
    print(f"\n所有类别概率:")
    for label, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        print(f"  {label}: {prob:.4f}")
