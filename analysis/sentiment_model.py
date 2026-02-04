import os
import numpy as np
import onnxruntime as ort
from transformers import BertTokenizer


class SentimentModel:
    _instance = None

    def __new__(cls ,*args,**kwargs):
        if not cls._instance:
            cls._instance = super(SentimentModel,cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path=None):
        if hasattr(self,'initialized') and self.initialized:
            return

        # 默认使用 models 目录下的模型
        if model_path is None:
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "text_sentiment", "text_sentiment_model.onnx")

        print(f"正在加载模型: {model_path}")

        # tokenizer 从 .onnx 同目录加载（export_onnx.py 会将 tokenizer 保存到同目录）
        tokenizer_dir = os.path.dirname(model_path)
        self.tokenizer = BertTokenizer.from_pretrained(tokenizer_dir)

        # ONNX Runtime 推理会话
        self.session = ort.InferenceSession(model_path)
        # 获取模型需要的输入名称
        self.input_names = [inp.name for inp in self.session.get_inputs()]

        self.initialized = True

    def predict(self, text_list, batch_size=32):
        """
        批量预测一组文本的情感（分 mini-batch 防 OOM）
        :param text_list: 字符串列表
        :param batch_size: 每个 mini-batch 的大小
        :return: 情感得分列表 (0~1)
        """
        if not text_list:
            return []

        all_scores = []
        for i in range(0, len(text_list), batch_size):
            batch = text_list[i:i + batch_size]

            # 1. 编码与对齐
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="np"
            )

            # 2. 构造 ONNX Runtime 输入
            ort_inputs = {}
            for name in self.input_names:
                if name in inputs:
                    ort_inputs[name] = inputs[name]
                elif name == "token_type_ids":
                    # 部分 tokenizer 不返回 token_type_ids，手动补零
                    ort_inputs[name] = np.zeros_like(inputs["input_ids"])

            # 3. 推理
            logits = self.session.run(None, ort_inputs)[0]

            # 4. softmax → 提取正面情感概率 (label 1)
            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

            all_scores.extend(probs[:, 1].tolist())

        return all_scores
