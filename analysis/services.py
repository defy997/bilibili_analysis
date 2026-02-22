"""
数据处理服务模块
包含数据爬取、数据清洗、情感分析等逻辑
"""
import os
import re
import datetime
import tempfile
import unicodedata
import threading
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from .sentiment_model import SentimentModel
from .models import Video, Comment, Danmu, UserConfig

# ============================================================
# SESSDATA 管理
# ============================================================

def get_sessdata_from_db():
    """
    从数据库获取有效的 SESSDATA
    
    Returns:
        str: SESSDATA cookie 字符串，如果无效则返回 None
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # 查找有 bilibili 凭证的用户
        user = User.objects.filter(
            bilibili_mid__isnull=False,
            sessdata__isnull=False
        ).first()
        
        if not user or not user.sessdata:
            return None
        
        # 验证 SESSDATA 是否有效
        try:
            from .sessdata_manager import SessdataManager
            manager = SessdataManager(user)
            result = manager.check_sessdata_valid()
            
            if result.get('valid') and not result.get('need_refresh'):
                return f"SESSDATA={user.sessdata}"
            
            # 如果需要刷新，尝试自动刷新
            if result.get('need_refresh'):
                refresh_result = manager.refresh_sessdata()
                if refresh_result['success']:
                    # 刷新成功后重新获取
                    user.refresh_from_db()
                    return f"SESSDATA={user.sessdata}"
        except Exception as e:
            print(f"[get_sessdata_from_db] 验证 SESSDATA 失败: {e}")
        
        return None
    except Exception as e:
        print(f"[get_sessdata_from_db] 获取 SESSDATA 失败: {e}")
        return None


def ensure_valid_cookie():
    """
    确保获取到有效的 Cookie
    
    Returns:
        str: 可用的 Cookie 字符串
    """
    # 1. 尝试从数据库获取
    sessdata = get_sessdata_from_db()
    if sessdata:
        return sessdata
    
    # 2. 返回硬编码的默认值（作为 fallback）
    print("[ensure_valid_cookie] 数据库中无可用 SESSDATA，使用默认配置")
    return "SESSDATA=55d2ed48%2C1785846835%2Cd80a0%2A22CjDxZL1htFveMUpzPXZrxp6zwh1K5neWuRyhGlZxWZ1A3xBGw6NIs8AhnyqkO5tfmBgSVmhQTHVlNDNaMzlENjNqYjQwcGNPRzN5T05YcTN3SFRLT2ZvOW9sZHFvS295WmdRdW1YQXZzc01GMEdBek1YTGZTajNINW1jdmhRaUN4MWV6QnFLcGh3IIEC"


# 视频处理锁，防止同一视频被并发分析
_video_processing_locks = {}
_locks_lock = threading.Lock()

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
    MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "text_sentiment", "text_sentiment_model.onnx")
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


CPP_CRAWLER_URL = 'http://localhost:8081'


def check_sessdata_and_refresh(force_refresh=False):
    """
    检查 SESSDATA 是否有效，如果无效或过期则尝试刷新
    
    Args:
        force_refresh: 是否强制刷新
        
    Returns:
        dict: {
            'valid': bool,           # SESSDATA 是否有效
            'message': str,          # 状态信息
            'need_login': bool,      # 是否需要重新登录
            'sessdata': str or None  # 有效的 SESSDATA（如果需要返回）
        }
    """
    from .sessdata_manager import SessdataManager
    
    manager = SessdataManager()
    
    # 先检查当前 SESSDATA 是否有效
    check_result = manager.check_sessdata_valid()
    
    if check_result['valid'] and not force_refresh:
        if not check_result.get('need_refresh', False):
            return {
                'valid': True,
                'message': 'SESSDATA 有效',
                'need_login': False,
                'sessdata': None
            }
        else:
            # 需要刷新
            print("[Sessdata] SESSDATA 需要刷新，尝试刷新...")
            refresh_result = manager.refresh_sessdata()
            if refresh_result['success']:
                return {
                    'valid': True,
                    'message': 'SESSDATA 已刷新',
                    'need_login': False,
                    'sessdata': None
                }
            else:
                return {
                    'valid': False,
                    'message': f'刷新失败: {refresh_result["message"]}',
                    'need_login': True,
                    'sessdata': None
                }
    else:
        # SESSDATA 无效，需要登录
        return {
            'valid': False,
            'message': check_result.get('message', 'SESSDATA 无效'),
            'need_login': True,
            'sessdata': None
        }


def ensure_sessdata_valid():
    """
    确保 SESSDATA 有效，如果无效则抛出异常
    
    Raises:
        Exception: 如果 SESSDATA 无效且无法刷新
    """
    result = check_sessdata_and_refresh()
    if not result['valid']:
        raise Exception(f"SESSDATA 无效: {result['message']}，请先登录绑定 B 站账号")


def _crawl_audio_url_python(bvid, cid, headers, max_retries=3, retry_delay=5):
    """Python fallback: 获取B站音频流URL"""
    import time
    
    url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&fnver=0&fourk=1"
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            
            if data['code'] == 0:
                audio_list = data['data']['dash']['audio']
                audio_list.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)
                best = audio_list[0]
                return {
                    'audio_url': best['baseUrl'],
                    'codec': best.get('codecs', ''),
                    'bandwidth': best.get('bandwidth', 0)
                }
            elif 'request was banned' in data.get('message', ''):
                # 被限制，等待后重试
                if attempt < max_retries - 1:
                    print(f"[playurl] 请求被限制，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
            # 其他错误直接抛出
            raise Exception(f"playurl API error: {data['message']}")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"[playurl] 请求超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            raise Exception("playurl API timeout")
    
    raise Exception(f"playurl API error: 达到最大重试次数 ({max_retries})")


def crawl_audio_url(bvid, cid, headers, cookie):
    """获取音频流URL，C++ 优先，Python fallback"""
    try:
        resp = requests.post(f'{CPP_CRAWLER_URL}/crawl/audio-url',
                             json={'bvid': bvid, 'cid': cid, 'cookie': cookie}, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get('success'):
                return data['data']
    except Exception as e:
        print(f"C++ audio-url service failed: {e}")
    return _crawl_audio_url_python(bvid, cid, headers)


def _crawl_video_info_python(bvid, headers, cookie):
    """
    爬取视频基本信息（Python 实现）
    """
    video_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    resp = requests.get(video_url, headers=headers)
    data = resp.json()

    if data['code'] != 0:
        raise Exception(f"获取视频信息失败: {data['message']}")

    stat = data['data'].get('stat', {})
    return {
        'aid': data["data"]["aid"],
        'cid': data['data']['cid'],
        'title': data['data']['title'],
        'pubdate_ts': data['data'].get('pubdate'),
        'reply_count': stat.get('reply', 0),
        # 新增：视频统计数据
        'view': stat.get('view', 0),
        'like': stat.get('like', 0),
        'coin': stat.get('coin', 0),
        'favorite': stat.get('favorite', 0),
        'share': stat.get('share', 0)
    }


def crawl_video_info(bvid, headers, cookie):
    """
    爬取视频基本信息，优先使用 C++ 服务，失败则 fallback 到 Python
    """
    try:
        resp = requests.post(f'{CPP_CRAWLER_URL}/crawl/video',
                             json={'bvid': bvid, 'cookie': cookie}, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get('success'):
                print("[crawl_video_info] 使用 C++ 爬虫服务")
                return data['data']
    except Exception as e:
        print(f"[crawl_video_info] C++ 服务不可用({e})，使用 Python fallback")
    return _crawl_video_info_python(bvid, headers, cookie)


def check_need_refresh(bvid, headers, cookie, threshold=0.1):
    """
    检查视频评论数据是否需要刷新
    对比B站远程评论总数与本地数据库评论数，差异超过阈值则需要刷新

    Args:
        threshold: 差异比例阈值，默认10%（远程比本地多10%以上就刷新）

    Returns:
        (need_refresh, video_info) — 是否需要刷新 + 视频信息
    """
    video_info = crawl_video_info(bvid, headers, cookie)
    remote_count = video_info.get('reply_count', 0)

    # 用原始爬取数对比，而非清洗后的数量
    try:
        video = Video.objects.get(bvid=bvid)
        local_count = video.raw_comment_count
    except Video.DoesNotExist:
        local_count = 0

    # 只要本地有数据，就不重新爬取
    if local_count > 0:
        print(f"[刷新检测] 本地已有数据，无需刷新")
        return False, video_info

    print(f"[刷新检测] 本地无数据，需要爬取")
    return True, video_info


def _crawl_comments_python(aid, headers):
    """
    爬取视频全部评论（Python 实现，使用游标分页，带重试和反风控）
    """
    import time
    import random

    all_comments = []
    next_cursor = 0
    page = 0
    max_retries = 3
    comment_api = "https://api.bilibili.com/x/v2/reply/main"

    while True:
        page += 1
        params = {
            "type": 1,
            "oid": aid,
            "mode": 3,
            "next": next_cursor
        }

        for retry in range(max_retries):
            try:
                comment_resp = requests.get(comment_api, params=params, headers=headers, timeout=15)
                comment_data = comment_resp.json()

                if comment_data['code'] != 0:
                    print(f"评论API返回错误码: {comment_data['code']}")
                    return all_comments

                data = comment_data.get('data', {})
                replies = data.get('replies', [])
                if not replies:
                    print(f"评论爬取完成: 共{len(all_comments)}条")
                    return all_comments

                all_comments.extend(replies)

                # 使用API返回的游标值翻页
                cursor = data.get('cursor', {})
                is_end = cursor.get('is_end', True)
                next_cursor = cursor.get('next', 0)

                print(f"第{page}页: 获取{len(replies)}条评论，累计{len(all_comments)}条")

                if is_end:
                    print(f"评论爬取完成: 共{len(all_comments)}条")
                    return all_comments

                # 随机请求间隔 0.5~1.5s，避免固定节奏被风控
                time.sleep(random.uniform(0.5, 1.5))
                break  # 请求成功，跳出重试循环

            except Exception as e:
                print(f"获取第{page}页评论出错 (重试 {retry+1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    wait = (retry + 1) * 5 + random.uniform(1, 3)
                    print(f"等待 {wait:.1f}s 后重试...")
                    time.sleep(wait)
                else:
                    print(f"第{page}页重试耗尽，已获取{len(all_comments)}条评论")
                    return all_comments

    print(f"评论爬取完成: 共{len(all_comments)}条")
    return all_comments


def _cpp_comment_to_bilibili_format(c):
    """
    将 C++ 服务返回的扁平评论格式转换回 Bilibili API 的嵌套格式，
    以兼容 save_comment 等下游函数
    """
    return {
        'rpid': c.get('rpid'),
        'mid': c.get('mid', 0),
        'parent': c.get('parent', 0),
        'like': c.get('like', 0),
        'rcount': c.get('rcount', 0),
        'ctime': c.get('ctime', 0),
        'content': {'message': c.get('message', '')},
        'member': {
            'uname': c.get('uname', ''),
            'vip': {
                'vipType': c.get('vip_type', 0),
                'label': {'text': c.get('vip_label', '')}
            }
        },
        'reply_control': {'location': c.get('location', '')}
    }


def crawl_comments(aid, headers):
    """
    爬取视频全部评论，优先使用 C++ 服务，失败则 fallback 到 Python
    """
    cookie = headers.get('cookie', '')
    try:
        resp = requests.post(f'{CPP_CRAWLER_URL}/crawl/comments',
                             json={'aid': aid, 'cookie': cookie}, timeout=300)
        if resp.ok:
            data = resp.json()
            if data.get('success'):
                print(f"[crawl_comments] 使用 C++ 爬虫服务，获取 {data.get('total', 0)} 条评论")
                return [_cpp_comment_to_bilibili_format(c) for c in data['data']]
    except Exception as e:
        print(f"[crawl_comments] C++ 服务不可用({e})，使用 Python fallback")
    return _crawl_comments_python(aid, headers)


def _crawl_danmaku_python(cid, headers):
    """
    爬取视频弹幕（Python 实现）
    返回格式: [{
        'content': str,
        'video_time': float,    # 视频内出现时间（秒）
        'send_time': int,       # 真实发送时间戳
        'user_hash': str        # 用户Hash
    }, ...]
    """
    import datetime
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
                    # 从 p 属性中提取信息
                    # p 格式: "时间,模式,字号,颜色,时间戳,弹幕池,用户hash,弹幕ID"
                    p_attr = element.get('p', '')
                    video_time = 0.0
                    send_timestamp = None
                    user_hash = None

                    if p_attr:
                        try:
                            parts = p_attr.split(',')
                            video_time = float(parts[0]) if parts[0] else 0.0
                            send_timestamp = int(parts[4]) if len(parts) > 4 and parts[4] else None
                            user_hash = parts[6] if len(parts) > 6 and parts[6] else None
                        except (ValueError, IndexError):
                            video_time = 0.0
                            send_timestamp = None
                            user_hash = None

                    danmaku_list.append({
                        'content': text,
                        'video_time': video_time,
                        'send_time': send_timestamp,
                        'user_hash': user_hash
                    })

        print(f"获取到 {len(danmaku_list)} 条弹幕")
    except Exception as e:
        print(f"获取弹幕失败: {e}")

    return danmaku_list


def crawl_danmaku(cid, headers):
    """
    爬取视频弹幕，优先使用 C++ 服务，失败或返回空则 fallback 到 Python
    """
    cookie = headers.get('cookie', '')
    try:
        resp = requests.post(f'{CPP_CRAWLER_URL}/crawl/danmaku',
                             json={'cid': cid, 'cookie': cookie}, timeout=30)
        if resp.ok:
            data = resp.json()
            if data.get('success') and data.get('total', 0) > 0:
                print(f"[crawl_danmaku] 使用 C++ 爬虫服务，获取 {data.get('total', 0)} 条弹幕")
                return data['data']
            else:
                print(f"[crawl_danmaku] C++ 服务返回 0 条弹幕，使用 Python fallback")
    except Exception as e:
        print(f"[crawl_danmaku] C++ 服务不可用({e})，使用 Python fallback")
    return _crawl_danmaku_python(cid, headers)


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
            'pubdate': pubdate_dt,
            'raw_comment_count': video_info.get('reply_count', 0),  # 保存评论数
            # 新增：视频统计数据
            'view': video_info.get('view', 0),
            'like': video_info.get('like', 0),
            'coin': video_info.get('coin', 0),
            'favorite': video_info.get('favorite', 0),
            'share': video_info.get('share', 0)
        }
    )
    if created:
        print(f"新建视频记录: {video_info['title']}, 评论数: {video_info.get('reply_count', 0)}")
    else:
        # 更新已存在的视频的统计数据
        video_obj.raw_comment_count = video_info.get('reply_count', 0)
        video_obj.view = video_info.get('view', 0)
        video_obj.like = video_info.get('like', 0)
        video_obj.coin = video_info.get('coin', 0)
        video_obj.favorite = video_info.get('favorite', 0)
        video_obj.share = video_info.get('share', 0)
        video_obj.save(update_fields=['raw_comment_count', 'view', 'like', 'coin', 'favorite', 'share'])

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

        # 提取用户等级（新版B站API在member中，备用从mid获取）
        member_info = comment_data.get('member', {})
        user_level = member_info.get('level', 0)
        if not user_level:
            # 兼容旧版API结构
            user_level = comment_data.get('user_level', 0)

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
                'user_level': user_level,
                'parent_rpid': parent_rpid,
                'sentiment_score': score,
                'sentiment_label': sentiment_label
            }
        )
        return comment
    except Exception as e:
        print(f"保存评论失败 (rpid={comment_data.get('rpid')}): {e}")
        return None


def save_danmaku(cid, content, score, sentiment_label, video_time=0.0, send_time=None, user_hash=None):
    """
    保存单条弹幕到数据库（集成数据清洗和过滤）

    Args:
        cid: 视频CID
        content: 弹幕内容
        score: 情感得分
        sentiment_label: 情感分类
        video_time: 视频内出现时间（秒）
        send_time: 真实发送时间（DateTimeField，可为None）
        user_hash: 发送者Hash值
    """
    import datetime
    from django.utils import timezone

    try:
        # 数据清洗（用于展示的版本）
        cleaned_content = clean_text(content, for_analysis=False)

        # 数据过滤：检查清洗后的文本是否有意义
        if not is_meaningful_text(cleaned_content):
            # 弹幕过滤不打印日志（数量太多）
            return None

        # 转换 send_time 时间戳为 DateTimeField
        send_time_dt = None
        if send_time:
            try:
                naive_dt = datetime.datetime.fromtimestamp(send_time)
                send_time_dt = timezone.make_aware(naive_dt)
            except:
                send_time_dt = None

        Danmu.objects.create(
            cid=cid,
            content=cleaned_content,
            video_time=video_time,
            send_time=send_time_dt,
            user_hash=user_hash,
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


def is_video_processing(bvid):
    """
    检查视频是否正在被处理中（不阻塞）
    
    Args:
        bvid: 视频BV号
        
    Returns:
        bool: True 表示视频正在被处理，False 表示未被处理
    """
    with _locks_lock:
        if bvid not in _video_processing_locks:
            return False
        lock = _video_processing_locks[bvid]
        # 尝试非阻塞获取锁来判断是否正在处理
        if lock.acquire(blocking=False):
            lock.release()
            return False
        return True


def process_video(bvid, headers, cookie):
    """
    处理单个视频：爬取 -> 清洗 -> 分析 -> 保存
    使用锁防止同一视频被并发处理
    """
    # 获取该视频专属锁
    with _locks_lock:
        if bvid not in _video_processing_locks:
            _video_processing_locks[bvid] = threading.Lock()
        lock = _video_processing_locks[bvid]

    # 非阻塞尝试获取锁
    if not lock.acquire(blocking=False):
        print(f"[跳过] 视频 {bvid} 正在被其他请求处理，等待结果...")
        # 阻塞等待处理完成
        with lock:
            pass
        # 处理已完成，直接返回缓存标记
        return {"status": "already_processing"}

    try:
        print(f"开始处理视频: {bvid}")

        # 1. 爬取视频信息
        video_info = crawl_video_info(bvid, headers, cookie)
        video_obj = save_video(video_info, bvid)

        # 2. 爬取评论和弹幕
        all_comments = crawl_comments(video_info['aid'], headers)
        danmaku_list = crawl_danmaku(video_info['cid'], headers)

        # 记录原始爬取评论数
        video_obj.raw_comment_count = len(all_comments)
        video_obj.save(update_fields=['raw_comment_count'])

        # 3. 数据清洗和过滤（评论）
        analysis_comments = []
        valid_comment_indices = []

        for i, comment in enumerate(all_comments):
            message = comment.get('content', {}).get('message', '')
            if message:
                cleaned = clean_text(message, for_analysis=True)
                if is_meaningful_text(cleaned):
                    analysis_comments.append(cleaned)
                    valid_comment_indices.append(i)

        # 数据清洗和过滤（弹幕）
        analysis_danmu = []
        valid_danmu_indices = []

        for i, danmaku in enumerate(danmaku_list):
            content = danmaku.get('content', '') if isinstance(danmaku, dict) else str(danmaku)
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

        # 5. 情感分析（优先 Celery 并行，不可用时回退同步）
        CHUNK_SIZE = 64
        celery_available = False
        try:
            import redis as _redis
            _r = _redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
            _r.ping()
            celery_available = True
        except Exception:
            pass

        if celery_available:
            try:
                from .tasks import analyze_sentiment_chunk
                from celery import group

                chunks = [raw_texts[i:i + CHUNK_SIZE] for i in range(0, len(raw_texts), CHUNK_SIZE)]
                print(f"Submitting {len(chunks)} chunks to Celery")
                job = group(analyze_sentiment_chunk.s(chunk) for chunk in chunks)
                result = job.apply_async()
                chunk_scores = result.get(timeout=300)
                scores = [s for chunk in chunk_scores for s in chunk]
            except Exception as e:
                print(f"Celery 任务执行失败({e})，回退同步分析")
                scores = analyze_sentiment(raw_texts)
        else:
            print("Redis 不可达，直接使用同步分析")
            scores = analyze_sentiment(raw_texts)

        # 6. 保存结果
        comment_count = 0
        for analysis_idx, original_idx in enumerate(valid_comment_indices):
            comment = all_comments[original_idx]
            score = scores[analysis_idx] if analysis_idx < len(scores) else 0.5
            sentiment = get_sentiment_label(score)
            result = save_comment(comment, video_obj, score, sentiment)
            if result:
                comment_count += 1

        danmu_count = 0
        base_idx = len(analysis_comments)
        for analysis_idx, original_idx in enumerate(valid_danmu_indices):
            danmu_item = danmaku_list[original_idx]
            # 兼容新旧数据格式
            if isinstance(danmu_item, dict):
                content = danmu_item.get('content', '')
                video_time = danmu_item.get('video_time', 0.0)
                send_time = danmu_item.get('send_time', None)
                user_hash = danmu_item.get('user_hash', None)
            else:
                content = danmu_item
                video_time = 0.0
                send_time = None
                user_hash = None

            score_idx = base_idx + analysis_idx
            score = scores[score_idx] if score_idx < len(scores) else 0.5
            sentiment = get_sentiment_label(score)
            result = save_danmaku(video_info['cid'], content, score, sentiment, video_time, send_time, user_hash)
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
    finally:
        lock.release()
        with _locks_lock:
            _video_processing_locks.pop(bvid, None)


def download_audio(audio_url, save_path):
    """
    下载B站音频流到本地文件

    :param audio_url: 音频流URL
    :param save_path: 保存路径
    :return: 保存路径
    """
    resp = requests.get(
        audio_url,
        stream=True,
        headers={
            'Referer': 'https://www.bilibili.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        timeout=120,
    )
    resp.raise_for_status()

    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return save_path


def analyze_video_audio(bvid, headers, cookie, segment_duration=15, overlap=5):
    """
    完整的视频音频情感分析流程

    1. 检查缓存 → 有数据直接返回
    2. 获取音频URL → 下载 → 分段分析 → 批量写入DB
    3. 返回 timeline 数据

    :param bvid: 视频BV号
    :param headers: 请求头
    :param cookie: B站Cookie
    :param segment_duration: 分段时长（秒）
    :param overlap: 重叠时长（秒）
    :return: dict with timeline data
    """
    from .models import Video, AudioSentiment

    # 1. 检查缓存
    try:
        video = Video.objects.get(bvid=bvid)
    except Video.DoesNotExist:
        video_info = crawl_video_info(bvid, headers, cookie)
        video = save_video(video_info, bvid)

    existing = AudioSentiment.objects.filter(video=video)
    if existing.exists():
        timeline = [
            {
                'time_offset': s.time_offset,
                'label': s.sentiment_label,
                'score': s.sentiment_score,
                'probabilities': s.emotion_probs,
                'segment_duration': s.segment_duration,
            }
            for s in existing
        ]
        return {'status': 'cached', 'timeline': timeline}

    # 2. 获取音频URL
    if not video.cid:
        raise Exception(f"视频 {bvid} 缺少 cid 信息")

    audio_info = crawl_audio_url(bvid, video.cid, headers, cookie)
    audio_url = audio_info.get('audio_url')
    if not audio_url:
        raise Exception(f"无法获取视频 {bvid} 的音频URL")

    # 3. 下载到临时文件
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.m4a')
    os.close(tmp_fd)
    # 转换为 wav 格式供 librosa 读取
    wav_path = tempfile.mktemp(suffix='.wav')

    try:
        print(f"[AudioAnalysis] 下载音频: {bvid}")
        download_audio(audio_url, tmp_path)

        # 使用 ffmpeg 转换为 wav 格式
        import subprocess
        print(f"[AudioAnalysis] 转换音频格式: m4a -> wav")
        subprocess.run([
            'ffmpeg', '-y', '-i', tmp_path, '-ar', '16000', '-ac', '1', wav_path
        ], check=True, capture_output=True)

        # 4. 分段分析
        print(f"[AudioAnalysis] 开始分段分析: {bvid}")
        from .audio_sentiment_model import AudioSentimentModel
        model = AudioSentimentModel()
        segments = model.analyze_segments(
            wav_path,
            segment_duration=segment_duration,
            overlap=overlap,
        )

        if not segments:
            return {'status': 'no_audio_data', 'timeline': []}

        # 5. 批量写入数据库
        #    sentiment_score 存情感极性（0=消极,1=积极），不存置信度
        audio_objects = [
            AudioSentiment(
                video=video,
                time_offset=seg['time_offset'],
                sentiment_score=seg['sentiment_score'],
                sentiment_label=get_sentiment_label(seg['sentiment_score']),
                emotion_probs=seg['probabilities'],
                segment_duration=seg['segment_duration'],
            )
            for seg in segments
        ]
        AudioSentiment.objects.bulk_create(audio_objects)
        print(f"[AudioAnalysis] 写入 {len(audio_objects)} 条音频情感数据: {bvid}")

        # 6. 返回 timeline
        timeline = [
            {
                'time_offset': seg['time_offset'],
                'label': get_sentiment_label(seg['sentiment_score']),
                'score': seg['sentiment_score'],
                'emotion': seg['label'],
                'probabilities': seg['probabilities'],
                'segment_duration': seg['segment_duration'],
            }
            for seg in segments
        ]
        return {'status': 'success', 'timeline': timeline}

    finally:
        # 7. 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)

