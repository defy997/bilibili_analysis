# 数据清洗模块 - 阶段一使用指南

## 概述

本项目已集成完整的数据清洗功能（阶段一），包括：
- ✅ Unicode标准化（全角/半角转换）
- ✅ OpenCC繁简转换
- ✅ Emoji和表情符号清理
- ✅ 重复字符压缩
- ✅ 基础数据过滤（长度、垃圾内容、中文占比）
- ✅ 完整的清洗流水线

## 安装依赖

### 1. 安装Python包

```bash
pip install -r requirements.txt
```

主要新增依赖：
- `opencc-python-reimplemented`: 繁简转换

### 2. 验证安装

运行测试脚本：

```bash
cd D:\code\python\bilibili_analysis
python analysis\test_cleaning.py
```

## 功能说明

### 1. 文本标准化

#### normalize_unicode(text)
Unicode规范化，统一全角/半角字符

```python
from analysis.services import normalize_unicode

text = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
result = normalize_unicode(text)  # "Hello World"
```

#### convert_traditional_to_simplified(text)
繁体转简体（使用OpenCC）

```python
from analysis.services import convert_traditional_to_simplified

text = "資料清洗測試"
result = convert_traditional_to_simplified(text)  # "资料清洗测试"
```

#### remove_emoji(text)
移除Unicode emoji和B站表情

```python
from analysis.services import remove_emoji

text = "哈哈哈😂😂😂[doge]"
result = remove_emoji(text)  # "哈哈哈"
```

#### compress_repeated_chars(text, max_repeat=3)
压缩重复字符

```python
from analysis.services import compress_repeated_chars

text = "哈哈哈哈哈哈哈哈"
result = compress_repeated_chars(text, max_repeat=3)  # "哈哈哈"
```

### 2. 完整清洗函数

#### clean_text(text, for_analysis=False)
增强版数据清洗，集成所有清洗功能

**参数：**
- `text`: 原始文本
- `for_analysis`: 是否用于情感分析
  - `False`: 用于展示，去除更多无意义符号
  - `True`: 用于分析，保留可能有情感倾向的符号（如"~"、"…"）

**示例：**

```python
from analysis.services import clean_text

text = "【視頻】這個視頻太棒了！！！！https://bilibili.com @用户名 #话题#"

# 用于展示
display_text = clean_text(text, for_analysis=False)
# 结果: "这个视频太棒了!"

# 用于分析
analysis_text = clean_text(text, for_analysis=True)
# 结果: "这个视频太棒了！！！！"（保留情感相关的符号）
```

**清洗流程：**
1. Unicode标准化
2. 繁体转简体
3. 去除URL
4. 去除@用户名
5. 去除话题标签
6. 去除emoji表情
7. 去除多余空白字符
8. 去除特殊符号（根据场景不同）
9. 压缩重复字符
10. 去除首尾空白

### 3. 数据过滤

#### filter_by_length(text, min_length=2, max_length=500)
长度过滤

```python
from analysis.services import filter_by_length

text = "a"
is_valid = filter_by_length(text)  # False (太短)
```

#### is_spam_content(text)
垃圾内容检测

检测规则：
- 纯数字
- 纯符号
- 单字符重复（如"啊啊啊啊啊啊啊"）
- 字符种类太少（unique_ratio < 0.3）

```python
from analysis.services import is_spam_content

text = "12345678"
is_spam = is_spam_content(text)  # True
```

#### get_chinese_ratio(text)
计算中文字符占比

```python
from analysis.services import get_chinese_ratio

text = "这是中文 This is English"
ratio = get_chinese_ratio(text)  # 约0.4 (40%)
```

#### is_meaningful_text(text, min_chinese_ratio=0.3)
综合判断文本是否有意义

检查项：
- 长度是否合理（2-500字符）
- 是否为垃圾内容
- 中文占比是否达标（长文本）

```python
from analysis.services import is_meaningful_text

text = "这是一条正常的评论"
is_valid = is_meaningful_text(text)  # True
```

## 集成到爬虫流程

数据清洗已自动集成到`process_video()`函数中：

```python
from analysis.services import process_video

# 处理视频（自动进行数据清洗和过滤）
result = process_video(
    bvid="BV1xx411c7XZ",
    headers=headers,
    cookie=cookie
)
```

**自动处理流程：**

1. 爬取原始数据
2. 用`clean_text(text, for_analysis=True)`清洗用于情感分析的文本
3. 用`is_meaningful_text()`过滤无效数据
4. 只对有效数据进行情感分析
5. 用`clean_text(text, for_analysis=False)`清洗用于存储的文本
6. 保存到数据库

**统计信息：**
```python
{
    "status": "success",
    "title": "视频标题",
    "positive_count": 120,
    "neutral_count": 50,
    "negative_count": 30,
    "comment_count": 180,  # 保存到数据库的评论数（已过滤）
    "danmu_count": 450     # 保存到数据库的弹幕数（已过滤）
}
```

## 配置选项

### 修改过滤参数

在 `analysis/services.py` 中可以调整过滤参数：

```python
# 长度过滤
def filter_by_length(text, min_length=2, max_length=500):
    # 修改 min_length 和 max_length

# 中文占比
def is_meaningful_text(text, min_chinese_ratio=0.3):
    # 修改 min_chinese_ratio（0.0-1.0）

# 重复字符压缩
def compress_repeated_chars(text, max_repeat=3):
    # 修改 max_repeat
```

## 数据质量对比

### 清洗前：
```
原文: 【視頻】這個視頻太棒了！！！！😂😂https://bilibili.com @用户名 #话题#
```

### 清洗后（展示）：
```
结果: 这个视频太棒了!
```

### 清洗后（分析）：
```
结果: 这个视频太棒了！！！！
```

## 常见问题

### Q1: OpenCC加载失败怎么办？
**A:** 如果OpenCC加载失败，繁简转换功能会被禁用，但不影响其他功能。检查：
```bash
pip install opencc-python-reimplemented
```

### Q2: 为什么有些评论没有保存？
**A:** 评论可能被过滤器过滤掉了，原因可能是：
- 长度不符合要求（<2 或 >500字符）
- 被识别为垃圾内容（纯数字、纯符号、重复字符等）
- 中文占比过低（长文本）

查看日志中的"评论被过滤"信息。

### Q3: 如何调整过滤严格度？
**A:** 修改 `is_meaningful_text()` 中的参数：
- 降低 `min_chinese_ratio`（如0.3 -> 0.1）：允许更多英文内容
- 修改 `filter_by_length()` 的 `min_length`：允许更短的评论
- 注释掉 `is_spam_content()` 检查：保留所有内容（不推荐）

## 下一步计划

### 阶段二：进阶清洗（待实现）
- 文本精确去重
- 质量评分系统
- 模糊去重（编辑距离）

### 阶段三：高级清洗（待实现）
- Embedding语义去重
- 完整Pipeline类
- 批量处理优化

## 文件位置

- 主要代码: `analysis/services.py`
- 测试脚本: `analysis/test_cleaning.py`
- 依赖文件: `requirements.txt`
- 使用指南: `DATA_CLEANING_GUIDE.md`（本文件）

## 联系与反馈

如有问题或建议，请在项目中提出Issue。
