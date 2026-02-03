"""
将 SpeechEmotionRecognition-Pytorch 的 BiLSTM 模型导出为 ONNX 格式。

用法：
    python scripts/export_audio_onnx.py [--model_path PATH] [--output_path PATH]

导出后，生成：
    - audio_emotion_model.onnx: ONNX 模型
    - label_list.txt: 标签列表
    - scaler.pkl: 归一化器
"""
import argparse
import os
import sys
import pickle

import numpy as np
import torch
import torch.nn as nn
import yaml

# SpeechEmotionRecognition-Pytorch 项目路径
# 需要根据实际情况修改为正确的路径
SER_PROJECT = r"D:\code\python\SpeechEmotionRecognition-Pytorch"
sys.path.insert(0, SER_PROJECT)

from mser.models.bi_lstm import BiLSTM
from mser.data_utils.featurizer import AudioFeaturizer
from mser.utils.utils import dict_to_object


class BiLSTMForONNX(nn.Module):
    """包装LSTM 模型用于 ONNX  Bi导出"""
    
    def __init__(self, input_size, num_classes, hidden_dim=256):
        super().__init__()
        self.fc0 = nn.Linear(in_features=input_size, out_features=512)
        self.lstm = nn.LSTM(input_size=512, hidden_size=hidden_dim, bidirectional=True)
        self.tanh = nn.Tanh()
        self.dropout = nn.Dropout(p=0.5)
        self.fc1 = nn.Linear(in_features=512, out_features=256)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(in_features=256, out_features=num_classes)
    
    def forward(self, x):
        # x: (batch, feature_dim)
        x = self.fc0(x)  # (batch, 512)
        x = x.unsqueeze(dim=1)  # (batch, 1, 512)
        y, (h, c) = self.lstm(x)  # y: (batch, 1, 512)
        x = y.squeeze(axis=1)  # (batch, 512)
        x = self.tanh(x)
        x = self.dropout(x)
        x = self.fc1(x)
        x = self.relu1(x)
        x = self.fc2(x)
        return x


def load_scaler(scaler_path):
    """加载归一化器"""
    with open(scaler_path, 'rb') as f:
        return pickle.load(f)


def export_onnx(
    model_path: str,
    config_path: str,
    scaler_path: str,
    label_list_path: str,
    output_path: str,
    opset: int = 14
):
    """导出音频情感模型为 ONNX"""
    
    print(f"加载配置: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.load(f.read(), Loader=yaml.FullLoader)
    config = dict_to_object(config)
    
    # 加载标签
    print(f"加载标签: {label_list_path}")
    with open(label_list_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    class_labels = [l.replace('\n', '') for l in lines]
    num_classes = len(class_labels)
    print(f"类别数: {num_classes}")
    print(f"标签: {class_labels}")
    
    # 获取特征维度
    featurizer = AudioFeaturizer(
        feature_method=config.preprocess_conf.feature_method,
        method_args=config.preprocess_conf.get('method_args', {})
    )
    feature_dim = featurizer.feature_dim
    print(f"特征维度: {feature_dim}")
    
    # 加载 PyTorch 模型
    print(f"加载模型: {model_path}")
    model = BiLSTM(input_size=feature_dim, num_class=num_classes)
    model_state_dict = torch.load(model_path, map_location='cpu', weights_only=False)
    model.load_state_dict(model_state_dict)
    model.eval()
    
    # 创建 ONNX 兼容模型
    onnx_model = BiLSTMForONNX(
        input_size=feature_dim,
        num_classes=num_classes,
        hidden_dim=256
    )
    onnx_model.load_state_dict(model.state_dict())
    onnx_model.eval()
    
    # 构造 dummy 输入
    dummy_input = torch.randn(1, feature_dim)
    
    # 导出 ONNX
    print(f"导出 ONNX (opset {opset}) → {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    torch.onnx.export(
        onnx_model,
        dummy_input,
        output_path,
        opset_version=opset,
        input_names=["features"],
        output_names=["logits"],
        dynamic_axes={
            "features": {0: "batch"},
            "logits": {0: "batch"},
        },
    )
    print("ONNX 导出完成")
    
    # ---- 验证 ----
    import onnxruntime as ort
    
    session = ort.InferenceSession(output_path)
    
    # 测试推理
    test_input = torch.randn(1, feature_dim).numpy()
    
    with torch.no_grad():
        pt_logits = onnx_model(torch.tensor(test_input)).numpy()
    
    ort_inputs = {"features": test_input}
    ort_logits = session.run(None, ort_inputs)[0]
    
    max_diff = np.max(np.abs(pt_logits - ort_logits))
    print(f"PyTorch vs ONNX 最大差异: {max_diff:.6e}")
    
    if max_diff < 1e-5:
        print("验证通过 ✓")
    else:
        print(f"警告：差异 {max_diff:.6e} 超过 1e-5，请检查模型")
        sys.exit(1)
    
    # 保存辅助文件
    output_dir = os.path.dirname(output_path)
    
    # 保存标签列表
    label_path = os.path.join(output_dir, "audio_label_list.txt")
    with open(label_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(class_labels))
    print(f"标签列表已保存到: {label_path}")
    
    # 复制归一化器
    import shutil
    scaler_dest = os.path.join(output_dir, "audio_scaler.pkl")
    shutil.copy(scaler_path, scaler_dest)
    print(f"归一化器已保存到: {scaler_dest}")
    
    return output_path


def main():
    # bilibili_analysis 项目根目录
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    default_model = os.path.join(
        SER_PROJECT,
        "models/BiLSTM_Emotion2Vec/best_model/model.pth"
    )
    default_config = os.path.join(SER_PROJECT, "configs/bi_lstm.yml")
    default_scaler = os.path.join(SER_PROJECT, "dataset/standard.m")
    default_labels = os.path.join(SER_PROJECT, "dataset/label_list.txt")
    default_output = os.path.join(PROJECT_ROOT, "models", "audio_emotion", "audio_emotion_model.onnx")
    
    parser = argparse.ArgumentParser(description="导出音频情感模型为 ONNX")
    parser.add_argument("--model_path", default=default_model, help="PyTorch 模型文件路径")
    parser.add_argument("--config_path", default=default_config, help="配置文件路径")
    parser.add_argument("--scaler_path", default=default_scaler, help="归一化器文件路径")
    parser.add_argument("--label_list_path", default=default_labels, help="标签列表文件路径")
    parser.add_argument("--output_path", default=default_output, help="ONNX 输出路径")
    parser.add_argument("--opset", type=int, default=14, help="ONNX opset 版本")
    args = parser.parse_args()
    
    # 检查文件是否存在
    for path, name in [
        (args.model_path, "模型"),
        (args.config_path, "配置"),
        (args.scaler_path, "归一化器"),
        (args.label_list_path, "标签列表"),
    ]:
        if not os.path.exists(path):
            print(f"错误: {name} 路径不存在: {path}")
            sys.exit(1)
    
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    
    export_onnx(
        args.model_path,
        args.config_path,
        args.scaler_path,
        args.label_list_path,
        args.output_path,
        args.opset
    )


if __name__ == "__main__":
    main()
