# 数据清洗模块完整指南 - 阶段一、二、三

## 目录
- [概述](#概述)
- [安装依赖](#安装依赖)
- [阶段一：基础清洗](#阶段一基础清洗)
- [阶段二：去重和质量评分](#阶段二去重和质量评分)
- [阶段三：高级功能](#阶段三高级功能)
- [使用示例](#使用示例)
- [配置说明](#配置说明)

---

## 概述

本项目已实现完整的三阶段数据清洗功能：

### 阶段一：基础清洗
- ✅ Unicode标准化（全角/半角转换）
- ✅ OpenCC繁简转换
- ✅ Emoji和表情符号清理
- ✅ 重复字符压缩
- ✅ 基础数据过滤（长度、垃圾内容、中文占比）

### 阶段二：去重和质量评分
- ✅ 文本精确去重（基于哈希）
- ✅ 模糊去重（基于编辑距离）
- ✅ 质量评分系统

### 阶段三：高级功能
- ✅ Embedding语义去重（基于sentence-transformers）
- ✅ 完整Pipeline类
- ✅ 批量处理优化

---

## 安装依赖

### 1. 安装Python包

```bash
pip install -r requirements.txt
```

主要依赖：
- `opencc-python-reimplemented`: 繁简转换
- `sentence-transformers`: Embedding模型（语义去重）
- `scikit-learn`: 余弦相似度计算

### 2. 验证安装

运行完整测试：

```bash
cd D:\code\python\bilibili_analysis
python analysis\test_cleaning.py
```

---

## 阶段一：基础清洗

### 1.1 文本标准化

#### normalize_unicode(text)
```python
from analysis.services import normalize_unicode

text = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
result = normalize_unicode(text)  # "Hello World"
```

#### convert_traditional_to_simplified(text)
```python
from analysis.services import convert_traditional_to_simplified

text = "資料清洗測試"
result = convert_traditional_to_simplified(text)  # "资料清洗测试"
```

#### remove_emoji(text)
```python
from analysis.services import remove_emoji

text = "哈哈哈😂😂😂[doge]"
result = remove_emoji(text)  # "哈哈哈"
```

#### compress_repeated_chars(text, max_repeat=3)
```python
from analysis.services import compress_repeated_chars

text = "哈哈哈哈哈哈哈哈"
result = compress_repeated_chars(text, max_repeat=3)  # "哈哈哈"
```

### 1.2 完整清洗函数

#### clean_text(text, for_analysis=False)

**用于展示：**
```python
text = "【視頻】這個視頻太棒了！！！！https://bilibili.com @用户名"
result = clean_text(text, for_analysis=False)
# 结果: "这个视频太棒了!"
```

**用于分析：**
```python
result = clean_text(text, for_analysis=True)
# 结果: "这个视频太棒了！！！！" (保留情感符号)
```

### 1.3 数据过滤

#### filter_by_length(text, min_length=2, max_length=500)
```python
from analysis.services import filter_by_length

is_valid = filter_by_length("正常评论")  # True
is_valid = filter_by_length("a")  # False
```

#### is_spam_content(text)
```python
from analysis.services import is_spam_content

is_spam = is_spam_content("12345678")  # True
is_spam = is_spam_content("正常评论")  # False
```

#### is_meaningful_text(text)
```python
from analysis.services import is_meaningful_text

is_valid = is_meaningful_text("这是一条正常的评论")  # True
is_valid = is_meaningful_text("！！！")  # False
```

---

## 阶段二：去重和质量评分

### 2.1 精确去重

#### exact_dedup(text_list, metadata_list=None)

基于MD5哈希的精确去重，保留质量最高（如点赞数最多）的样本。

```python
from analysis.services import exact_dedup

texts = [
    "这是重复的评论",
    "这是另一条评论",
    "这是重复的评论",  # 重复
]
metadata = [5, 10, 8]  # 点赞数

unique_indices, dup_groups = exact_dedup(texts, metadata)
# unique_indices: [0, 1] (保留了点赞数更高的第一条)
# dup_groups: {hash: [0, 2]}
```

### 2.2 模糊去重

#### fuzzy_dedup(text_list, threshold=0.85, metadata_list=None)

基于编辑距离（SequenceMatcher）的模糊去重，识别高度相似的文本。

```python
from analysis.services import fuzzy_dedup

texts = [
    "这个视频真不错",
    "这个视频真的不错",  # 相似
    "完全不同的评论",
]

unique_indices, sim_groups = fuzzy_dedup(texts, threshold=0.7)
# unique_indices: [0, 2] (合并了相似的前两条)
# sim_groups: [[0, 1]]
```

**阈值说明：**
- `0.9-1.0`: 极高相似（几乎相同）
- `0.8-0.9`: 高相似（推荐）
- `0.7-0.8`: 中等相似
- `< 0.7`: 低相似（可能误判）

### 2.3 质量评分

#### calculate_quality_score(text, like_count=0, ...)

综合评分系统（0-1分），考虑：
- 长度合理性（30%）
- 点赞数（30%）
- 中文占比（20%）
- 内容有意义性（20%）

```python
from analysis.services import calculate_quality_score

score = calculate_quality_score("正常的评论内容", like_count=10)
# score: 0.75

score = calculate_quality_score("a", like_count=0)
# score: 0.1 (太短)

score = calculate_quality_score("非常棒的视频！", like_count=100)
# score: 0.9+ (高赞+优质内容)
```

---

## 阶段三：高级功能

### 3.1 Embedding语义去重

#### load_embedding_model(model_name='paraphrase-multilingual-MiniLM-L12-v2')

加载多语言Embedding模型（首次使用会自动下载）。

```python
from analysis.services import load_embedding_model

model = load_embedding_model()
# 推荐模型：paraphrase-multilingual-MiniLM-L12-v2 (轻量级)
```

#### embedding_dedup(text_list, threshold=0.85, metadata_list=None, batch_size=32)

基于语义向量的去重，识别表述不同但意思相同的内容。

```python
from analysis.services import embedding_dedup

texts = [
    "这个视频真不错",
    "这视频挺好的",  # 语义相似
    "完全不同的内容",
]

unique_indices, sim_groups = embedding_dedup(texts, threshold=0.85)
# 自动识别语义相似的评论
```

**优势：**
- 识别语义相似但表述不同的内容
- 支持中英文混合
- 适合检测机器人刷屏（同义改写）

**性能：**
- 首次加载模型需要下载（约100MB）
- 批量处理速度快（支持GPU加速）

### 3.2 完整Pipeline类

#### DataCleaningPipeline

整合所有清洗、过滤、去重功能的Pipeline类。

**基础用法：**

```python
from analysis.services import DataCleaningPipeline

# 创建Pipeline
pipeline = DataCleaningPipeline()

# 添加数据
texts = ["评论1", "评论2", ...]
metadata = [10, 5, ...]  # 点赞数

pipeline.add_texts(texts, metadata)

# 执行清洗流程
pipeline.clean()          # 文本清洗
pipeline.filter()         # 数据过滤
pipeline.calculate_quality()  # 质量评分
pipeline.deduplicate()    # 去重

# 获取结果
results = pipeline.get_results()
pipeline.print_report()   # 打印清洗报告
```

**高级配置：**

```python
config = {
    'clean_for_analysis': False,      # 是否用于分析
    'min_length': 2,                  # 最小长度
    'max_length': 500,                # 最大长度
    'min_chinese_ratio': 0.3,         # 最小中文占比
    'min_quality_score': 0.3,         # 最小质量分
    'dedup_method': 'embedding',      # 去重方法: exact/fuzzy/embedding/all
    'fuzzy_threshold': 0.85,          # 模糊去重阈值
    'embedding_threshold': 0.85,      # 语义去重阈值
}

pipeline = DataCleaningPipeline(config)
```

**链式调用：**

```python
results = (DataCleaningPipeline(config)
    .add_texts(texts, metadata)
    .clean()
    .filter()
    .calculate_quality()
    .deduplicate(method='all')  # 应用所有去重方法
    .get_results())
```

---

## 使用示例

### 示例1：基础清洗

```python
from analysis.services import clean_text, is_meaningful_text

text = "【視頻】這個視頻太棒了！！！！😂😂"

# 清洗
cleaned = clean_text(text, for_analysis=False)
# 结果: "这个视频太棒了!"

# 验证
if is_meaningful_text(cleaned):
    print("有效评论")
```

### 示例2：去重 + 质量评分

```python
from analysis.services import exact_dedup, calculate_quality_score

texts = ["评论1", "评论2", "评论1"]  # 有重复
likes = [10, 5, 3]

# 精确去重
unique_indices, _ = exact_dedup(texts, likes)

# 计算质量分
for idx in unique_indices:
    score = calculate_quality_score(texts[idx], likes[idx])
    print(f"{texts[idx]}: 质量分 {score}")
```

### 示例3：完整Pipeline

```python
from analysis.services import DataCleaningPipeline

# 模拟B站评论数据
comments = [
    "【視頻】這個視頻太棒了！！！！😂😂",
    "這個視頻太棒了！！！！",  # 相似
    "a",  # 太短
    "这是一条正常的评论",
    "这是一条正常的评论",  # 重复
]
likes = [10, 5, 0, 8, 3]

# 创建Pipeline
config = {
    'min_quality_score': 0.3,
    'dedup_method': 'all',  # 应用所有去重方法
}

pipeline = DataCleaningPipeline(config)

# 执行
results = (pipeline
    .add_texts(comments, likes)
    .clean()
    .filter()
    .calculate_quality()
    .deduplicate()
    .get_results())

# 查看结果
for text, score in zip(results['texts'], results['quality_scores']):
    print(f"{text} (质量: {score:.2f})")

# 打印报告
pipeline.print_report()
```

**输出示例：**
```
数据清洗报告
============================================================
原始数据: 5条
清洗后: 5条
过滤后: 3条
去重后: 2条

过滤详情:
  - 长度不符: 1条
  - 垃圾内容: 0条
  - 中文占比低: 0条
  - 质量不达标: 1条
  - 重复内容: 1条

最终保留率: 40.0%
============================================================
```

---

## 配置说明

### Pipeline配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `clean_for_analysis` | bool | False | 是否用于分析（True保留更多符号） |
| `min_length` | int | 2 | 最小文本长度 |
| `max_length` | int | 500 | 最大文本长度 |
| `min_chinese_ratio` | float | 0.3 | 最小中文占比（0-1） |
| `min_quality_score` | float | 0.3 | 最小质量评分（0-1） |
| `dedup_method` | str | 'exact' | 去重方法：exact/fuzzy/embedding/all |
| `fuzzy_threshold` | float | 0.85 | 模糊去重相似度阈值（0-1） |
| `embedding_threshold` | float | 0.85 | 语义去重相似度阈值（0-1） |

### 去重方法对比

| 方法 | 速度 | 准确度 | 适用场景 |
|------|------|--------|----------|
| `exact` | 极快 | 完美 | 完全相同的文本 |
| `fuzzy` | 快 | 高 | 文字相似（错别字、标点差异） |
| `embedding` | 慢 | 很高 | 语义相似（同义改写） |
| `all` | 慢 | 最高 | 综合去重（推荐） |

### 质量评分权重

- 长度合理性：30%（理想5-200字符）
- 点赞数：30%（log归一化，100赞为满分）
- 中文占比：20%（中文>=50%为满分）
- 内容有意义性：20%（字符多样性）

---

## 集成到爬虫流程

数据清洗已自动集成到`process_video()`函数：

```python
from analysis.services import process_video

result = process_video(
    bvid="BV1xx411c7XZ",
    headers=headers,
    cookie=cookie
)

print(f"处理完成: {result['comment_count']}条评论，{result['danmu_count']}条弹幕")
```

**自动处理流程：**
1. 爬取原始数据
2. 清洗（阶段一）
3. 过滤无效数据
4. 情感分析
5. 保存到数据库

**注意：** Pipeline方式需要手动调用，不会自动集成到爬虫流程。

---

## 性能优化建议

### 1. 批量处理
```python
# 使用Pipeline批量处理大量数据
pipeline = DataCleaningPipeline()
pipeline.add_texts(large_text_list, metadata_list)
pipeline.clean().filter().deduplicate(method='exact')  # 先用快速方法
```

### 2. 选择合适的去重方法
- 小数据量（<1000）：使用 `all`
- 中等数据量（1000-10000）：使用 `fuzzy`
- 大数据量（>10000）：使用 `exact`

### 3. Embedding模型优化
```python
# 首次使用会下载模型，建议提前加载
from analysis.services import load_embedding_model
model = load_embedding_model()  # 预加载

# 如果有GPU，会自动使用GPU加速
```

---

## 常见问题

### Q1: OpenCC加载失败？
**A:** 检查安装：
```bash
pip install opencc-python-reimplemented
```

### Q2: Embedding模型下载慢？
**A:** 模型会自动下载到 `~/.cache/huggingface/`，可以：
1. 使用国内镜像
2. 手动下载模型文件
3. 使用更小的模型

### Q3: 如何调整过滤严格度？
**A:** 修改Pipeline配置：
```python
config = {
    'min_length': 1,          # 允许更短
    'min_chinese_ratio': 0.1, # 允许更多英文
    'min_quality_score': 0.2, # 降低质量要求
}
```

### Q4: 去重太慢？
**A:**
1. 先使用 `exact_dedup`（最快）
2. 减小数据量再用 `embedding_dedup`
3. 调整 `batch_size` 参数

---

## 文件位置

- **主要代码**: `analysis/services.py`
- **测试脚本**: `analysis/test_cleaning.py`
- **依赖文件**: `requirements.txt`
- **完整指南**: `DATA_CLEANING_COMPLETE_GUIDE.md`（本文件）

---

## 版本历史

- **v3.0 (阶段三)**: 添加Embedding语义去重、完整Pipeline类
- **v2.0 (阶段二)**: 添加精确/模糊去重、质量评分系统
- **v1.0 (阶段一)**: 基础清洗、Unicode标准化、繁简转换

---

## 下一步开发计划

- [ ] 支持自定义去重策略
- [ ] 添加更多质量评分维度
- [ ] 性能进一步优化
- [ ] Web界面可视化

---

如有问题或建议，请在项目中提出Issue。
