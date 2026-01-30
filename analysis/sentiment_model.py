import os
import torch
from transformers import BertTokenizer, BertForSequenceClassification
import torch.nn.functional as F
class SentimentModel:
    _instance = None

    def __new__(cls ,*args,**kwargs):
        if not cls._instance:
            cls._instance = super(SentimentModel,cls).__new__(cls)
        return cls._instance
    
    def __init__(self, model_path=None):
        if hasattr(self,'initialized') and self.initialized:
            return

        # 默认使用最新训练的模型
        if model_path is None:
            # 自动选择 checkpoints 目录下最新的模型
            checkpoints_dir = r"D:\code\python\bert-model-train\checkpoints_hotel_finetuned\best_model_epoch_3.pt"
            if os.path.exists(checkpoints_dir):
                import glob
                checkpoints = glob.glob(os.path.join(checkpoints_dir, '*.pt'))
                if checkpoints:
                    # 按修改时间排序
                    checkpoints.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    model_path = checkpoints[0]
                    print(f"自动选择模型: {os.path.basename(model_path)}")
                else:
                    model_path = r"D:\code\python\bert-model-train\checkpoints_hotel_finetuned\best_model_epoch_2.pt"
            else:
                model_path = r"D:\code\python\bert-model-train\checkpoints_hotel_finetuned\best_model_epoch_2.pt"

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"正在加载模型: {model_path}")
        print(f"设备: {self.device}")
        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.model = BertForSequenceClassification.from_pretrained(model_path)
        self.model.to(self.device)
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
                return_tensors="pt"
            ).to(self.device)

            # 2. 推理
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = F.softmax(outputs.logits, dim=1)

            # 3. 提取正面情感的概率 (假设 label 1 是正面)
            all_scores.extend(probs[:, 1].tolist())

        return all_scores