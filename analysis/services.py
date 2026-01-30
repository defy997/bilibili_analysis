"""
数据处理服务模块
包含数据爬取、数据清洗、情感分析等逻辑
"""
import re
import datetime
import unicodedata
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from .sentiment_model import SentimentModel
from .models import Video, Comment, Danmu, UserConfig

# 初始化OpenCC繁简转换
try:
    from opencc import OpenCC
    cc = OpenCC('t2s')  # 繁体转简体
    print("OpenCC加载成功")
except Exception as e:
    print(f"OpenCC加载失败: {e}, 繁简转换功能将被禁用")
    cc = None

# 初始化情感分析模型
try:
    MODEL_PATH = r"D:\code\python\bert-model-train\checkpoints_hotel_finetuned\best_model_epoch_3.pt"
    analyze = SentimentModel(MODEL_PATH)
except Exception as e:
    print(f"模型加载失败: {e}")
    analyze = None


# ============================================
# 数据清洗模块 - 阶段一
# ============================================

def normalize_unicode(text):
    """
    Unicode标准化：统一全角/半角字符
    """
    if not text:
        return ""

    # 1. Unicode规范化为NFC形式
    text = unicodedata.normalize('NFC', text)

    # 2. 全角转半角（数字、字母、常用符号）
    result = []
    for char in text:
        code = ord(char)
        # 全角空格单独处理
        if code == 0x3000:
            result.append(' ')
        # 全角字符（除空格）范围是 0xFF01-0xFF5E
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(char)

    return ''.join(result)


def convert_traditional_to_simplified(text):
    """
    OpenCC繁体转简体
    """
    if not text or cc is None:
        return text

    try:
        return cc.convert(text)
    except Exception as e:
        print(f"繁简转换失败: {e}")
        return text


def remove_emoji(text):
    """
    移除emoji表情符号（支持Unicode emoji）
    """
    if not text:
        return ""

    # 移除emoji表情的正则表达式
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和图标
        "\U0001F680-\U0001F6FF"  # 交通和地图符号
        "\U0001F1E0-\U0001F1FF"  # 旗帜
        "\U00002702-\U000027B0"  # 装饰符号
        "\U000024C2-\U000024FF"  # 封闭字母数字
        "\U0001F900-\U0001F9FF"  # 补充符号和图标
        "\U0001FA70-\U0001FAFF"  # 扩展符号
        "\U0001F004-\U0001F004"  # 麻将🀄
        "]+",
        flags=re.UNICODE
    )

    text = emoji_pattern.sub('', text)

    # 移除B站自带表情 [xxx]
    text = re.sub(r'\[.*?\]', '', text)

    return text


def compress_repeated_chars(text, max_repeat=3):
    """
    压缩重复字符
    例如："哈哈哈哈哈哈" -> "哈哈哈"
    """
    if not text:
        return ""

    result = []
    count = 1
    prev_char = ''

    for char in text:
        if char == prev_char:
            count += 1
            if count <= max_repeat:
                result.append(char)
        else:
            result.append(char)
            count = 1
            prev_char = char

    return ''.join(result)


def clean_text(text, for_analysis=False):
    """
    增强版数据清洗：去除无用字符，标准化文本

    Args:
        text: 原始文本
        for_analysis: 是否用于情感分析（True时保留更多语义信息）
    """
    if not text:
        return ""

    # 1. Unicode标准化
    text = normalize_unicode(text)

    # 2. 繁体转简体
    text = convert_traditional_to_simplified(text)

    # 3. 去除URL
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

    # 4. 去除@用户名
    text = re.sub(r'@[\w\u4e00-\u9fff]+', '', text)

    # 5. 去除话题标签 #xxx#
    text = re.sub(r'#[\w\u4e00-\u9fff]+#', '', text)

    # 6. 去除emoji表情
    text = remove_emoji(text)

    # 7. 去除多余空白字符
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*', '\n', text)
    text = re.sub(r'\n+', '\n', text)  # 多个换行符压缩为一个

    # 8. 去除特殊符号（保留基本标点）
    if not for_analysis:
        # 用于展示时，去除更多无意义符号
        text = re.sub(r'[^\w\s\u4e00-\u9fff，。！？、；：""''（）《》\[\],.!?\-]', '', text)
    else:
        # 用于分析时，保留可能有情感倾向的符号
        text = re.sub(r'[^\w\s\u4e00-\u9fff，。！？、；：""''（）《》\[\],.!?\-~…]', '', text)

    # 9. 压缩重复字符
    text = compress_repeated_chars(text, max_repeat=3)

    # 10. 去除首尾空白
    text = text.strip()

    return text


# ============================================
# 数据过滤模块
# ============================================

def filter_by_length(text, min_length=None, max_length=None):
    """
    长度过滤（从数据库读取默认配置）
    """
    if not text:
        return False

    # 从数据库读取配置
    if min_length is None or max_length is None:
        try:
            config = UserConfig.get_config()
            if min_length is None:
                min_length = config.min_length
            if max_length is None:
                max_length = config.max_length
        except:
            # 数据库读取失败时使用默认值
            min_length = min_length or 1
            max_length = max_length or 500

    length = len(text)
    return min_length <= length <= max_length


def is_spam_content(text):
    """
    垃圾内容检测（从数据库读取配置）
    """
    if not text:
        return True

    # 从数据库读取配置
    try:
        config = UserConfig.get_config()
        max_char_repeat = config.max_char_repeat
        min_unique_ratio = config.min_unique_ratio
        min_unique_check_length = config.min_unique_check_length
    except:
        # 数据库读取失败时使用默认值
        max_char_repeat = 10
        min_unique_ratio = 0.2
        min_unique_check_length = 15

    # 1. 纯数字
    if text.isdigit():
        return True

    # 2. 纯符号（没有中英文字符）
    if not re.search(r'[\w\u4e00-\u9fff]', text):
        return True

    # 3. 单字符重复（如：啊啊啊啊啊啊啊啊啊啊）
    if len(set(text)) == 1 and len(text) > max_char_repeat:
        return True

    # 4. 字符种类太少（可能是无意义内容）
    unique_ratio = len(set(text)) / len(text)
    if len(text) > min_unique_check_length and unique_ratio < min_unique_ratio:
        return True

    return False


def get_chinese_ratio(text):
    """
    计算中文字符占比
    """
    if not text:
        return 0

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / len(text)


def is_meaningful_text(text, min_chinese_ratio=None, like_count=0, reply_count=0):
    """
    综合判断文本是否有意义（带白名单机制，从数据库读取配置）

    Args:
        text: 文本内容
        min_chinese_ratio: 最小中文占比（None 则从配置读取）
        like_count: 点赞数
        reply_count: 回复数/子评论数

    白名单规则（满足任一条件直接保留）：
        1. 点赞数 >= high_like_threshold → 高赞评论直接保留
        2. 回复数 >= high_reply_threshold → 热门讨论评论直接保留
        3. 点赞数 >= combined_like_threshold 且 回复数 >= combined_reply_threshold → 综合热度高的评论保留
    """
    if not text:
        return False

    # 从数据库读取配置
    try:
        config = UserConfig.get_config()
        if min_chinese_ratio is None:
            min_chinese_ratio = config.min_chinese_ratio
        high_like = config.high_like_threshold
        high_reply = config.high_reply_threshold
        combined_like = config.combined_like_threshold
        combined_reply = config.combined_reply_threshold
    except:
        # 数据库读取失败时使用默认值
        if min_chinese_ratio is None:
            min_chinese_ratio = 0.15
        high_like = 50
        high_reply = 10
        combined_like = 20
        combined_reply = 5

    # 【白名单机制】高赞或高回复评论直接通过
    if like_count >= high_like:
        return True  # 高赞评论
    if reply_count >= high_reply:
        return True  # 热门讨论
    if like_count >= combined_like and reply_count >= combined_reply:
        return True  # 综合热度高

    # 1. 长度检查
    if not filter_by_length(text):
        return False

    # 2. 垃圾内容检查
    if is_spam_content(text):
        return False

    # 3. 中文占比检查（B站主要是中文内容）
    chinese_ratio = get_chinese_ratio(text)
    if chinese_ratio < min_chinese_ratio and len(text) > 10:
        # 短文本可以容忍低中文占比（可能是英文或数字）
        return False

    return True


# ============================================
# 阶段二：去重模块
# ============================================

def text_hash(text):
    """
    计算文本哈希值（用于精确去重）
    """
    import hashlib
    if not text:
        return ""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def exact_dedup(text_list, metadata_list=None):
    """
    文本精确去重

    Args:
        text_list: 文本列表
        metadata_list: 元数据列表（如点赞数、时间等），用于选择保留哪个

    Returns:
        unique_indices: 保留的文本索引列表
        duplicate_groups: {hash: [indices]} 重复组
    """
    if not text_list:
        return [], {}

    hash_groups = {}  # {hash: [indices]}

    # 按哈希分组
    for i, text in enumerate(text_list):
        if not text:
            continue
        h = text_hash(text)
        if h not in hash_groups:
            hash_groups[h] = []
        hash_groups[h].append(i)

    # 选择保留的索引
    unique_indices = []
    duplicate_groups = {}

    for h, indices in hash_groups.items():
        if len(indices) == 1:
            # 唯一文本，直接保留
            unique_indices.append(indices[0])
        else:
            # 重复文本，选择质量最高的
            duplicate_groups[h] = indices

            if metadata_list:
                # 根据元数据选择最佳
                best_idx = indices[0]
                best_score = metadata_list[best_idx] if best_idx < len(metadata_list) else 0

                for idx in indices[1:]:
                    score = metadata_list[idx] if idx < len(metadata_list) else 0
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                unique_indices.append(best_idx)
            else:
                # 默认保留第一个
                unique_indices.append(indices[0])

    return sorted(unique_indices), duplicate_groups


def fuzzy_dedup(text_list, threshold=0.85, metadata_list=None):
    """
    模糊去重（基于编辑距离）

    Args:
        text_list: 文本列表
        threshold: 相似度阈值（0-1），超过此值视为重复
        metadata_list: 元数据列表（如点赞数），用于选择保留哪个

    Returns:
        unique_indices: 保留的文本索引列表
        similar_groups: [[indices]] 相似组列表
    """
    try:
        from difflib import SequenceMatcher
    except ImportError:
        print("警告: difflib不可用，跳过模糊去重")
        return list(range(len(text_list))), []

    if not text_list:
        return [], []

    n = len(text_list)
    is_duplicate = [False] * n
    similar_groups = []
    unique_indices = []

    for i in range(n):
        if is_duplicate[i] or not text_list[i]:
            continue

        # 当前文本的相似组
        current_group = [i]

        # 与后续文本比较
        for j in range(i + 1, n):
            if is_duplicate[j] or not text_list[j]:
                continue

            # 计算相似度
            similarity = SequenceMatcher(None, text_list[i], text_list[j]).ratio()

            if similarity >= threshold:
                current_group.append(j)
                is_duplicate[j] = True

        # 如果有相似文本
        if len(current_group) > 1:
            similar_groups.append(current_group)

            # 选择质量最高的
            if metadata_list:
                best_idx = current_group[0]
                best_score = metadata_list[best_idx] if best_idx < len(metadata_list) else 0

                for idx in current_group[1:]:
                    score = metadata_list[idx] if idx < len(metadata_list) else 0
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                unique_indices.append(best_idx)
            else:
                unique_indices.append(current_group[0])
        else:
            unique_indices.append(i)

    return sorted(unique_indices), similar_groups


# ============================================
# 阶段二：质量评分模块
# ============================================

def calculate_quality_score(text, like_count=0, chinese_ratio=None, min_length=5, max_length=200):
    """
    计算文本质量评分（0-1）

    评分维度：
    1. 长度合理性（30%）：过短或过长都扣分
    2. 点赞数（30%）：归一化后的点赞数
    3. 中文占比（20%）：中文内容质量更高
    4. 内容有意义性（20%）：不是垃圾内容

    Args:
        text: 文本内容
        like_count: 点赞数
        chinese_ratio: 中文占比（可选，不提供则自动计算）
        min_length: 理想最小长度
        max_length: 理想最大长度

    Returns:
        float: 质量得分（0-1）
    """
    if not text:
        return 0.0

    score = 0.0

    # 1. 长度合理性得分（30%）
    text_len = len(text)
    if text_len < 2:
        length_score = 0.0
    elif text_len < min_length:
        length_score = text_len / min_length * 0.7  # 过短扣分
    elif text_len <= max_length:
        length_score = 1.0  # 理想长度
    else:
        # 过长扣分
        excess = text_len - max_length
        length_score = max(0.5, 1.0 - excess / max_length)

    score += length_score * 0.3

    # 2. 点赞数得分（30%）
    # 使用对数归一化，避免极端值影响
    import math
    if like_count > 0:
        # log(1+x)归一化，假设100赞为满分
        like_score = min(1.0, math.log(1 + like_count) / math.log(101))
    else:
        like_score = 0.1  # 0赞给基础分

    score += like_score * 0.3

    # 3. 中文占比得分（20%）
    if chinese_ratio is None:
        chinese_ratio = get_chinese_ratio(text)

    # 中文占比越高得分越高，但纯英文也给基础分
    if chinese_ratio >= 0.5:
        chinese_score = 1.0
    elif chinese_ratio >= 0.3:
        chinese_score = 0.8
    elif chinese_ratio > 0:
        chinese_score = 0.6
    else:
        chinese_score = 0.4  # 纯英文/数字

    score += chinese_score * 0.2

    # 4. 内容有意义性得分（20%）
    if is_spam_content(text):
        meaningful_score = 0.0
    else:
        # 字符多样性
        unique_ratio = len(set(text)) / len(text)
        meaningful_score = min(1.0, unique_ratio * 2)  # 多样性越高越好

    score += meaningful_score * 0.2

    return round(score, 3)


# ============================================
# 阶段三：Embedding语义去重模块
# ============================================

# 全局Embedding模型（延迟加载）
_embedding_model = None


def load_embedding_model(model_name='paraphrase-multilingual-MiniLM-L12-v2'):
    """
    加载Embedding模型（支持中英文）

    推荐模型：
    - paraphrase-multilingual-MiniLM-L12-v2: 轻量级多语言模型（推荐）
    - distiluse-base-multilingual-cased-v2: 更大的多语言模型
    """
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer
        print(f"正在加载Embedding模型: {model_name}")
        _embedding_model = SentenceTransformer(model_name)
        print("Embedding模型加载成功")
        return _embedding_model
    except ImportError:
        print("错误: 未安装sentence-transformers，请运行: pip install sentence-transformers")
        return None
    except Exception as e:
        print(f"Embedding模型加载失败: {e}")
        return None


def generate_embeddings(text_list, model=None, batch_size=32):
    """
    生成文本向量

    Args:
        text_list: 文本列表
        model: Embedding模型（可选）
        batch_size: 批处理大小

    Returns:
        numpy.ndarray: 文本向量矩阵 (n_texts, embedding_dim)
    """
    if not text_list:
        return None

    if model is None:
        model = load_embedding_model()

    if model is None:
        return None

    try:
        # 过滤空文本
        valid_texts = [text if text else "" for text in text_list]
        embeddings = model.encode(valid_texts, batch_size=batch_size, show_progress_bar=True)
        return embeddings
    except Exception as e:
        print(f"生成Embedding失败: {e}")
        return None


def embedding_dedup(text_list, threshold=0.85, metadata_list=None, batch_size=32):
    """
    基于Embedding的语义去重

    Args:
        text_list: 文本列表
        threshold: 余弦相似度阈值（0-1），超过此值视为语义重复
        metadata_list: 元数据列表（如点赞数），用于选择保留哪个
        batch_size: 批处理大小

    Returns:
        unique_indices: 保留的文本索引列表
        similar_groups: [[indices]] 语义相似组列表
    """
    if not text_list:
        return [], []

    # 生成embeddings
    embeddings = generate_embeddings(text_list, batch_size=batch_size)

    if embeddings is None:
        print("警告: Embedding生成失败，跳过语义去重")
        return list(range(len(text_list))), []

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        print("错误: 未安装scikit-learn，请运行: pip install scikit-learn")
        return list(range(len(text_list))), []

    # 计算余弦相似度矩阵
    similarity_matrix = cosine_similarity(embeddings)

    n = len(text_list)
    is_duplicate = [False] * n
    similar_groups = []
    unique_indices = []

    for i in range(n):
        if is_duplicate[i]:
            continue

        # 当前文本的相似组
        current_group = [i]

        # 查找与当前文本相似的其他文本
        for j in range(i + 1, n):
            if is_duplicate[j]:
                continue

            if similarity_matrix[i][j] >= threshold:
                current_group.append(j)
                is_duplicate[j] = True

        # 如果有语义相似文本
        if len(current_group) > 1:
            similar_groups.append(current_group)

            # 选择质量最高的
            if metadata_list:
                best_idx = current_group[0]
                best_score = metadata_list[best_idx] if best_idx < len(metadata_list) else 0

                for idx in current_group[1:]:
                    score = metadata_list[idx] if idx < len(metadata_list) else 0
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                unique_indices.append(best_idx)
            else:
                unique_indices.append(current_group[0])
        else:
            unique_indices.append(i)

    print(f"语义去重: {n}条 -> {len(unique_indices)}条，去除{n - len(unique_indices)}条重复")

    return sorted(unique_indices), similar_groups


# ============================================
# 阶段三：完整Pipeline类
# ============================================

class DataCleaningPipeline:
    """
    数据清洗Pipeline类

    功能：
    1. 文本清洗和标准化
    2. 数据过滤
    3. 质量评分
    4. 多种去重方式
    5. 清洗报告和统计

    用法：
        pipeline = DataCleaningPipeline()
        pipeline.add_texts(text_list, metadata_list)
        pipeline.clean()
        pipeline.filter()
        pipeline.deduplicate(method='embedding')
        results = pipeline.get_results()
    """

    def __init__(self, config=None):
        """
        初始化Pipeline（从数据库读取默认配置）

        Args:
            config: 配置字典（可选，用于覆盖默认配置）
        """
        # 从数据库读取默认配置
        try:
            db_config = UserConfig.get_config()
            self.config = {
                'clean_for_analysis': False,
                'min_length': db_config.min_length,
                'max_length': db_config.max_length,
                'min_chinese_ratio': db_config.min_chinese_ratio,
                'min_quality_score': db_config.min_quality_score,
                'dedup_method': db_config.dedup_method,
                'fuzzy_threshold': db_config.fuzzy_threshold,
                'embedding_threshold': db_config.embedding_threshold,
            }
        except:
            # 数据库读取失败时使用默认值
            self.config = {
                'clean_for_analysis': False,
                'min_length': 1,
                'max_length': 500,
                'min_chinese_ratio': 0.15,
                'min_quality_score': 0.2,
                'dedup_method': 'exact',
                'fuzzy_threshold': 0.85,
                'embedding_threshold': 0.85,
            }

        # 更新配置（如果提供了自定义配置）
        if config:
            self.config.update(config)

        # 数据存储
        self.original_texts = []
        self.cleaned_texts = []
        self.metadata = []
        self.quality_scores = []
        self.valid_indices = []  # 通过所有过滤的索引

        # 统计信息
        self.stats = {
            'original_count': 0,
            'after_clean': 0,
            'after_filter': 0,
            'after_dedup': 0,
            'removed_by_length': 0,
            'removed_by_spam': 0,
            'removed_by_chinese_ratio': 0,
            'removed_by_quality': 0,
            'removed_by_dedup': 0,
            'duplicate_groups': [],
        }

    def add_texts(self, text_list, metadata_list=None):
        """
        添加待处理文本

        Args:
            text_list: 文本列表
            metadata_list: 元数据列表（如点赞数、时间等）
        """
        self.original_texts = text_list
        self.stats['original_count'] = len(text_list)

        if metadata_list:
            self.metadata = metadata_list
        else:
            self.metadata = [0] * len(text_list)

        return self

    def clean(self):
        """
        文本清洗步骤
        """
        print("开始文本清洗...")

        for_analysis = self.config['clean_for_analysis']
        self.cleaned_texts = [
            clean_text(text, for_analysis=for_analysis)
            for text in self.original_texts
        ]

        self.stats['after_clean'] = len(self.cleaned_texts)
        print(f"清洗完成: {self.stats['original_count']}条文本")

        return self

    def filter(self):
        """
        数据过滤步骤
        """
        print("开始数据过滤...")

        filtered_indices = []

        for i, text in enumerate(self.cleaned_texts):
            # 长度过滤
            if not filter_by_length(text, self.config['min_length'], self.config['max_length']):
                self.stats['removed_by_length'] += 1
                continue

            # 垃圾内容过滤
            if is_spam_content(text):
                self.stats['removed_by_spam'] += 1
                continue

            # 中文占比过滤
            chinese_ratio = get_chinese_ratio(text)
            if len(text) > 10 and chinese_ratio < self.config['min_chinese_ratio']:
                self.stats['removed_by_chinese_ratio'] += 1
                continue

            filtered_indices.append(i)

        self.valid_indices = filtered_indices
        self.stats['after_filter'] = len(self.valid_indices)

        print(f"过滤完成: {self.stats['after_filter']}/{self.stats['original_count']}条通过")

        return self

    def calculate_quality(self):
        """
        计算质量评分
        """
        print("计算质量评分...")

        self.quality_scores = []

        for i in self.valid_indices:
            text = self.cleaned_texts[i]
            like_count = self.metadata[i] if i < len(self.metadata) else 0

            score = calculate_quality_score(
                text,
                like_count=like_count,
                min_length=self.config['min_length'],
                max_length=self.config['max_length']
            )

            self.quality_scores.append(score)

        # 按质量分过滤
        min_score = self.config['min_quality_score']
        before_count = len(self.valid_indices)

        filtered_indices = []
        filtered_scores = []

        for i, score in enumerate(self.quality_scores):
            if score >= min_score:
                filtered_indices.append(self.valid_indices[i])
                filtered_scores.append(score)
            else:
                self.stats['removed_by_quality'] += 1

        self.valid_indices = filtered_indices
        self.quality_scores = filtered_scores

        print(f"质量评分完成: {len(self.valid_indices)}/{before_count}条达标")

        return self

    def deduplicate(self, method=None):
        """
        去重步骤

        Args:
            method: 去重方法
                - 'exact': 精确去重
                - 'fuzzy': 模糊去重
                - 'embedding': 语义去重
                - 'all': 依次应用所有方法
        """
        if method is None:
            method = self.config['dedup_method']

        print(f"开始去重 (方法: {method})...")

        # 获取有效文本和元数据
        valid_texts = [self.cleaned_texts[i] for i in self.valid_indices]
        valid_metadata = [self.metadata[i] for i in self.valid_indices]

        before_count = len(valid_texts)

        if method == 'exact':
            unique_indices, dup_groups = exact_dedup(valid_texts, valid_metadata)
            self.stats['duplicate_groups'].extend(dup_groups.values())

        elif method == 'fuzzy':
            threshold = self.config['fuzzy_threshold']
            unique_indices, sim_groups = fuzzy_dedup(valid_texts, threshold, valid_metadata)
            self.stats['duplicate_groups'].extend(sim_groups)

        elif method == 'embedding':
            threshold = self.config['embedding_threshold']
            unique_indices, sim_groups = embedding_dedup(valid_texts, threshold, valid_metadata)
            self.stats['duplicate_groups'].extend(sim_groups)

        elif method == 'all':
            # 依次应用所有去重方法
            print("  - 应用精确去重...")
            unique_indices, dup_groups = exact_dedup(valid_texts, valid_metadata)
            self.stats['duplicate_groups'].extend(dup_groups.values())

            # 更新文本列表
            valid_texts = [valid_texts[i] for i in unique_indices]
            valid_metadata = [valid_metadata[i] for i in unique_indices]

            print("  - 应用模糊去重...")
            threshold = self.config['fuzzy_threshold']
            unique_indices2, sim_groups = fuzzy_dedup(valid_texts, threshold, valid_metadata)
            self.stats['duplicate_groups'].extend(sim_groups)

            # 映射回原始索引
            unique_indices = [unique_indices[i] for i in unique_indices2]

            # 更新文本列表
            valid_texts = [valid_texts[i] for i in unique_indices2]
            valid_metadata = [valid_metadata[i] for i in unique_indices2]

            print("  - 应用语义去重...")
            threshold = self.config['embedding_threshold']
            unique_indices3, sim_groups = embedding_dedup(valid_texts, threshold, valid_metadata)
            self.stats['duplicate_groups'].extend(sim_groups)

            # 映射回原始索引
            unique_indices = [unique_indices[i] for i in unique_indices3]

        else:
            print(f"未知的去重方法: {method}")
            return self

        # 更新有效索引
        self.valid_indices = [self.valid_indices[i] for i in unique_indices]
        self.quality_scores = [self.quality_scores[i] for i in unique_indices] if self.quality_scores else []

        self.stats['removed_by_dedup'] = before_count - len(self.valid_indices)
        self.stats['after_dedup'] = len(self.valid_indices)

        print(f"去重完成: {self.stats['after_dedup']}/{before_count}条保留")

        return self

    def get_results(self):
        """
        获取处理结果

        Returns:
            {
                'texts': [清洗后的文本],
                'original_indices': [原始索引],
                'quality_scores': [质量评分],
                'metadata': [元数据],
            }
        """
        results = {
            'texts': [self.cleaned_texts[i] for i in self.valid_indices],
            'original_indices': self.valid_indices,
            'quality_scores': self.quality_scores,
            'metadata': [self.metadata[i] for i in self.valid_indices],
        }

        return results

    def get_stats(self):
        """
        获取统计信息
        """
        return self.stats

    def print_report(self):
        """
        打印清洗报告
        """
        print("\n" + "=" * 60)
        print("数据清洗报告")
        print("=" * 60)
        print(f"原始数据: {self.stats['original_count']}条")
        print(f"清洗后: {self.stats['after_clean']}条")
        print(f"过滤后: {self.stats['after_filter']}条")
        print(f"去重后: {self.stats['after_dedup']}条")
        print("\n过滤详情:")
        print(f"  - 长度不符: {self.stats['removed_by_length']}条")
        print(f"  - 垃圾内容: {self.stats['removed_by_spam']}条")
        print(f"  - 中文占比低: {self.stats['removed_by_chinese_ratio']}条")
        print(f"  - 质量不达标: {self.stats['removed_by_quality']}条")
        print(f"  - 重复内容: {self.stats['removed_by_dedup']}条")
        print(f"\n最终保留率: {self.stats['after_dedup'] / self.stats['original_count'] * 100:.1f}%")
        print("=" * 60 + "\n")


def crawl_video_info(bvid, headers, cookie):
    """
    爬取视频基本信息
    """
    video_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    resp = requests.get(video_url, headers=headers)
    data = resp.json()

    if data['code'] != 0:
        raise Exception(f"获取视频信息失败: {data['message']}")

    return {
        'aid': data["data"]["aid"],
        'cid': data['data']['cid'],
        'title': data['data']['title'],
        'pubdate_ts': data['data'].get('pubdate')
    }


def crawl_comments(aid, headers, pages=3):
    """
    爬取视频评论
    """
    all_comments = []
    for page in range(1, pages + 1):
        comment_api = "https://api.bilibili.com/x/v2/reply/main"
        params = {
            "type": 1,
            "oid": aid,
            "next": page
        }
        try:
            comment_resp = requests.get(comment_api, params=params, headers=headers)
            comment_data = comment_resp.json()

            if comment_data['code'] != 0:
                break

            replies = comment_data['data'].get('replies', [])
            if not replies:
                break

            all_comments.extend(replies)
        except Exception as e:
            print(f"获取第{page}页评论出错: {e}")
            break

    return all_comments


def crawl_danmaku(cid, headers):
    """
    爬取视频弹幕
    """
    danmaku_list = []
    try:
        danmaku_api = f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}"
        danmaku_resp = requests.get(danmaku_api, headers=headers)

        if danmaku_resp.status_code == 200:
            soup = BeautifulSoup(danmaku_resp.content, 'xml')
            danmaku_elements = soup.find_all('d')

            for element in danmaku_elements:
                text = element.get_text(strip=True)
                if text:
                    danmaku_list.append(text)

        print(f"获取到 {len(danmaku_list)} 条弹幕")
    except Exception as e:
        print(f"获取弹幕失败: {e}")

    return danmaku_list


def save_video(video_info, bvid):
    """
    保存视频信息到数据库
    """
    pubdate_ts = video_info.get('pubdate_ts')
    pubdate_dt = None
    if pubdate_ts:
        try:
            naive_dt = datetime.datetime.fromtimestamp(pubdate_ts)
            pubdate_dt = timezone.make_aware(naive_dt)
        except:
            pass

    video_obj, created = Video.objects.get_or_create(
        bvid=bvid,
        defaults={
            'aid': video_info['aid'],
            'cid': video_info['cid'],
            'title': video_info['title'],
            'pubdate': pubdate_dt
        }
    )
    if created:
        print(f"新建视频记录: {video_info['title']}")

    return video_obj


def save_comment(comment_data, video_obj, score, sentiment_label):
    """
    保存单条评论到数据库（集成数据清洗和过滤）
    """
    try:
        # 提取字段
        rpid = comment_data.get('rpid')
        uname = comment_data.get('member', {}).get('uname', '')
        message = comment_data.get('content', {}).get('message', '')
        like_count = comment_data.get('like', 0)
        reply_count = comment_data.get('rcount', 0)  # 子评论数
        mid = comment_data.get('mid', 0)
        parent_rpid = comment_data.get('parent', 0)

        # 数据清洗（用于展示的版本）
        cleaned_message = clean_text(message, for_analysis=False)

        # 数据过滤：检查清洗后的文本是否有意义（带白名单机制）
        if not is_meaningful_text(cleaned_message, like_count=like_count, reply_count=reply_count):
            print(f"评论被过滤 (rpid={rpid}): 无意义内容 (赞:{like_count}, 回复:{reply_count})")
            return None

        # 提取身份标签
        vip_info = comment_data.get('member', {}).get('vip', {})
        vip_type = vip_info.get('vipType', 0)
        vip_label = vip_info.get('label', {}).get('text', '')

        # 处理时间
        ctime_ts = comment_data.get('ctime')
        ctime_dt = None
        if ctime_ts:
            try:
                naive_dt = datetime.datetime.fromtimestamp(ctime_ts)
                ctime_dt = timezone.make_aware(naive_dt)
            except:
                pass

        # IP属地
        location = comment_data.get('reply_control', {}).get('location', '未知')
        if "IP属地：" in location:
            location = location.replace("IP属地：", "")

        # 保存
        comment, _ = Comment.objects.update_or_create(
            rpid=rpid,
            defaults={
                'video': video_obj,
                'mid': mid,
                'uname': uname,
                'message': cleaned_message,
                'like_count': like_count,
                'reply_count': reply_count,  # 新增：子评论数
                'location': location,
                'ctime': ctime_dt,
                'vip_type': vip_type,
                'vip_label': vip_label,
                'parent_rpid': parent_rpid,
                'sentiment_score': score,
                'sentiment_label': sentiment_label
            }
        )
        return comment
    except Exception as e:
        print(f"保存评论失败 (rpid={comment_data.get('rpid')}): {e}")
        return None


def save_danmaku(cid, content, score, sentiment_label):
    """
    保存单条弹幕到数据库（集成数据清洗和过滤）
    """
    try:
        # 数据清洗（用于展示的版本）
        cleaned_content = clean_text(content, for_analysis=False)

        # 数据过滤：检查清洗后的文本是否有意义
        if not is_meaningful_text(cleaned_content):
            # 弹幕过滤不打印日志（数量太多）
            return None

        Danmu.objects.create(
            cid=cid,
            content=cleaned_content,
            sentiment_score=score,
            sentiment_label=sentiment_label
        )
        return True
    except Exception as e:
        print(f"保存弹幕失败: {e}")
        return None


def get_sentiment_label(score):
    """
    根据得分判断情感分类
    """
    if score >= 0.6:
        return "positive"
    elif score <= 0.4:
        return "negative"
    else:
        return "neutral"


def analyze_sentiment(text_list):
    """
    批量情感分析
    """
    if analyze is None:
        raise Exception("模型未加载成功")

    scores = analyze.predict(text_list)
    return scores


def process_video(bvid, headers, cookie):
    """
    处理单个视频：爬取 -> 清洗 -> 分析 -> 保存
    """
    print(f"开始处理视频: {bvid}")

    # 1. 爬取视频信息
    video_info = crawl_video_info(bvid, headers, cookie)
    video_obj = save_video(video_info, bvid)

    # 2. 爬取评论和弹幕
    all_comments = crawl_comments(video_info['aid'], headers)
    danmaku_list = crawl_danmaku(video_info['cid'], headers)

    # 3. 数据清洗和过滤（评论）
    # 用于分析的文本（保留更多语义信息）
    analysis_comments = []
    valid_comment_indices = []  # 记录有效评论的索引

    for i, comment in enumerate(all_comments):
        message = comment.get('content', {}).get('message', '')
        if message:
            cleaned = clean_text(message, for_analysis=True)
            if is_meaningful_text(cleaned):
                analysis_comments.append(cleaned)
                valid_comment_indices.append(i)

    # 3. 数据清洗和过滤（弹幕）
    analysis_danmu = []
    valid_danmu_indices = []  # 记录有效弹幕的索引

    for i, content in enumerate(danmaku_list):
        if content:
            cleaned = clean_text(content, for_analysis=True)
            if is_meaningful_text(cleaned):
                analysis_danmu.append(cleaned)
                valid_danmu_indices.append(i)

    # 4. 合并文本用于分析
    raw_texts = analysis_comments + analysis_danmu

    if not raw_texts:
        print("过滤后没有有效数据")
        return {"status": "no_data"}

    print(f"原始评论: {len(all_comments)}, 有效评论: {len(analysis_comments)}")
    print(f"原始弹幕: {len(danmaku_list)}, 有效弹幕: {len(analysis_danmu)}")

    # 5. 情感分析
    scores = analyze_sentiment(raw_texts)

    # 6. 保存结果
    # 保存评论（使用有效评论的索引）
    comment_count = 0
    for analysis_idx, original_idx in enumerate(valid_comment_indices):
        comment = all_comments[original_idx]
        score = scores[analysis_idx] if analysis_idx < len(scores) else 0.5
        sentiment = get_sentiment_label(score)
        result = save_comment(comment, video_obj, score, sentiment)
        if result:
            comment_count += 1

    # 保存弹幕（使用有效弹幕的索引）
    danmu_count = 0
    base_idx = len(analysis_comments)  # 弹幕的得分从评论之后开始
    for analysis_idx, original_idx in enumerate(valid_danmu_indices):
        content = danmaku_list[original_idx]
        score_idx = base_idx + analysis_idx
        score = scores[score_idx] if score_idx < len(scores) else 0.5
        sentiment = get_sentiment_label(score)
        result = save_danmaku(video_info['cid'], content, score, sentiment)
        if result:
            danmu_count += 1

    # 7. 统计结果
    positive_count = sum(1 for s in scores if s >= 0.6)
    negative_count = sum(1 for s in scores if s <= 0.4)
    neutral_count = len(scores) - positive_count - negative_count

    return {
        "status": "success",
        "title": video_info['title'],
        "positive_count": positive_count,
        "neutral_count": neutral_count,
        "negative_count": negative_count,
        "comment_count": comment_count,
        "danmu_count": danmu_count
    }

