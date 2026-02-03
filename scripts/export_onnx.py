"""
将 PyTorch BERT 情感分析模型导出为 ONNX 格式。

用法：
    python scripts/export_onnx.py [--model_path PATH] [--output_path PATH]

只需运行一次，生成 .onnx 文件后即可用 ONNX Runtime 推理。
"""
import argparse
import os
import sys

import numpy as np
import torch
from transformers import BertTokenizer, BertForSequenceClassification


def export_onnx(model_path: str, output_path: str, opset: int = 14):
    print(f"加载 PyTorch 模型: {model_path}")
    tokenizer = BertTokenizer.from_pretrained(model_path)
    model = BertForSequenceClassification.from_pretrained(model_path)
    model.eval()

    # 构造 dummy 输入
    dummy_text = "这是一条测试文本"
    inputs = tokenizer(
        dummy_text,
        padding="max_length",
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )

    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]
    token_type_ids = inputs.get("token_type_ids", torch.zeros_like(input_ids))

    # 导出
    print(f"导出 ONNX (opset {opset}) → {output_path}")
    torch.onnx.export(
        model,
        (input_ids, attention_mask, token_type_ids),
        output_path,
        opset_version=opset,
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "token_type_ids": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
    )
    print("ONNX 导出完成")

    # ---- 验证 ----
    import onnxruntime as ort

    session = ort.InferenceSession(output_path)

    # 用同一组输入跑 PyTorch 和 ONNX
    test_texts = ["这部电影很好看", "太差了，浪费时间", "一般般吧"]
    enc = tokenizer(
        test_texts,
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )

    with torch.no_grad():
        pt_logits = model(**enc).logits.numpy()

    ort_inputs = {
        "input_ids": enc["input_ids"].numpy(),
        "attention_mask": enc["attention_mask"].numpy(),
        "token_type_ids": enc.get("token_type_ids", torch.zeros_like(enc["input_ids"])).numpy(),
    }
    ort_logits = session.run(None, ort_inputs)[0]

    max_diff = np.max(np.abs(pt_logits - ort_logits))
    print(f"PyTorch vs ONNX 最大差异: {max_diff:.6e}")

    if max_diff < 1e-4:
        print("验证通过 ✓")
    else:
        print(f"警告：差异 {max_diff:.6e} 超过 1e-4，请检查模型")
        sys.exit(1)

    # 同时保存 tokenizer 到 onnx 输出目录（方便 ONNX Runtime 推理时加载）
    output_dir = os.path.dirname(output_path)
    tokenizer.save_pretrained(output_dir)
    print(f"Tokenizer 已保存到: {output_dir}")


def main():
    # bilibili_analysis 项目根目录
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 源模型路径（BERT 训练项目）
    default_model = r"D:\code\python\bert-model-train\checkpoints_hotel_finetuned\best_model_epoch_3.pt"

    # 输出到 bilibili_analysis 的 models 目录
    default_output = os.path.join(PROJECT_ROOT, "models", "text_sentiment", "text_sentiment_model.onnx")

    parser = argparse.ArgumentParser(description="导出 BERT 情感模型为 ONNX")
    parser.add_argument("--model_path", default=default_model, help="PyTorch 模型目录")
    parser.add_argument("--output_path", default=default_output, help="ONNX 输出路径")
    parser.add_argument("--opset", type=int, default=14, help="ONNX opset 版本")
    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"错误: 模型路径不存在: {args.model_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    export_onnx(args.model_path, args.output_path, args.opset)


if __name__ == "__main__":
    main()
