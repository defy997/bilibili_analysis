"""
数据清洗功能测试脚本
测试阶段一的各项功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_analysis.settings')
import django
django.setup()

from analysis.services import (
    normalize_unicode,
    convert_traditional_to_simplified,
    remove_emoji,
    compress_repeated_chars,
    clean_text,
    filter_by_length,
    is_spam_content,
    get_chinese_ratio,
    is_meaningful_text
)


def test_normalize_unicode():
    """测试Unicode规范化"""
    print("\n=== 测试Unicode规范化 ===")
    test_cases = [
        ("Ｈｅｌｌｏ　Ｗｏｒｌｄ", "Hello World"),
        ("１２３４５６７８９０", "1234567890"),
        ("！＠＃￥％", "!@#¥%"),
    ]
    for original, expected in test_cases:
        result = normalize_unicode(original)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{original}' -> '{result}'")


def test_convert_traditional():
    """测试繁简转换"""
    print("\n=== 测试繁简转换 ===")
    test_cases = [
        "資料清洗測試",
        "這個視頻真不錯",
        "繁體轉簡體",
    ]
    for text in test_cases:
        result = convert_traditional_to_simplified(text)
        print(f"'{text}' -> '{result}'")


def test_remove_emoji():
    """测试emoji移除"""
    print("\n=== 测试Emoji移除 ===")
    test_cases = [
        "哈哈哈😂😂😂",
        "太好了👍👍👍",
        "[doge]这个表情",
        "🎉🎉庆祝一下🎉🎉",
    ]
    for text in test_cases:
        result = remove_emoji(text)
        print(f"'{text}' -> '{result}'")


def test_compress_repeated():
    """测试重复字符压缩"""
    print("\n=== 测试重复字符压缩 ===")
    test_cases = [
        "哈哈哈哈哈哈哈哈哈",
        "太太太太太好了",
        "！！！！！！",
    ]
    for text in test_cases:
        result = compress_repeated_chars(text, max_repeat=3)
        print(f"'{text}' -> '{result}'")


def test_clean_text():
    """测试完整清洗流程"""
    print("\n=== 测试完整清洗流程 ===")
    test_cases = [
        "【視頻】這個視頻太棒了！！！！https://bilibili.com @用户名 #话题#",
        "Ｈｅｌｌｏ　Ｗｏｒｌｄ！！！這是繁體字😂😂😂",
        "[doge][doge]哈哈哈哈哈哈哈@someone #tag#",
        "   多余空格    和\n\n\n换行符   ",
    ]

    print("\n--- 用于展示的清洗 ---")
    for text in test_cases:
        result = clean_text(text, for_analysis=False)
        print(f"原文: {text}")
        print(f"结果: {result}\n")

    print("\n--- 用于分析的清洗 ---")
    for text in test_cases:
        result = clean_text(text, for_analysis=True)
        print(f"原文: {text}")
        print(f"结果: {result}\n")


def test_filters():
    """测试数据过滤"""
    print("\n=== 测试数据过滤 ===")

    print("\n--- 长度过滤 ---")
    test_cases = [
        ("a", False),
        ("正常长度的评论", True),
        ("这" + "是" * 300, False),  # 超长
    ]
    for text, expected in test_cases:
        result = filter_by_length(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text[:20]}...' -> {result} (预期: {expected})")

    print("\n--- 垃圾内容检测 ---")
    test_cases = [
        ("12345678", True),  # 纯数字
        ("！！！@#￥%", True),  # 纯符号
        ("啊啊啊啊啊啊啊", True),  # 单字符重复
        ("正常的评论内容", False),
        ("aaaaaaaabbbb", True),  # 字符种类太少
    ]
    for text, expected in test_cases:
        result = is_spam_content(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text}' -> 垃圾:{result} (预期: {expected})")

    print("\n--- 中文占比 ---")
    test_cases = [
        "这是中文评论",
        "Hello World",
        "中英混合 Mixed Content",
        "666666",
    ]
    for text in test_cases:
        ratio = get_chinese_ratio(text)
        print(f"'{text}' -> 中文占比: {ratio:.2%}")

    print("\n--- 综合有意义检测 ---")
    test_cases = [
        ("这是一条正常的评论", True),
        ("a", False),  # 太短
        ("12345678", False),  # 纯数字
        ("！！！！！", False),  # 纯符号
        ("Hello World Test", True),  # 英文也可以
        ("啊啊啊啊啊啊啊", False),  # 重复
    ]
    for text, expected in test_cases:
        result = is_meaningful_text(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text}' -> 有意义:{result} (预期: {expected})")


def test_dedup():
    """测试去重功能"""
    print("\n=== 测试去重功能（阶段二） ===")

    from analysis.services import exact_dedup, fuzzy_dedup, text_hash

    print("\n--- 文本哈希 ---")
    texts = ["这是测试", "这是测试", "这是不同的文本"]
    for text in texts:
        h = text_hash(text)
        print(f"'{text}' -> {h[:16]}...")

    print("\n--- 精确去重 ---")
    test_texts = [
        "这是重复的评论",
        "这是另一条评论",
        "这是重复的评论",  # 重复
        "完全不同的内容",
        "这是另一条评论",  # 重复
    ]
    metadata = [5, 10, 3, 7, 15]  # 点赞数

    unique_indices, dup_groups = exact_dedup(test_texts, metadata)
    print(f"原始: {len(test_texts)}条，去重后: {len(unique_indices)}条")
    print(f"保留的索引: {unique_indices}")
    print(f"重复组: {len(dup_groups)}组")

    print("\n--- 模糊去重 ---")
    test_texts2 = [
        "这个视频真不错",
        "这个视频真的不错",  # 相似
        "完全不同的评论",
        "这视频不错啊",  # 相似
        "另一条评论",
    ]

    unique_indices, sim_groups = fuzzy_dedup(test_texts2, threshold=0.7)
    print(f"原始: {len(test_texts2)}条，去重后: {len(unique_indices)}条")
    print(f"保留的索引: {unique_indices}")
    print(f"相似组: {len(sim_groups)}组")


def test_quality_score():
    """测试质量评分"""
    print("\n=== 测试质量评分（阶段二） ===")

    from analysis.services import calculate_quality_score

    test_cases = [
        ("正常的评论内容，长度适中", 10),
        ("a", 0),  # 太短
        ("这是一条很长很长的评论" * 50, 5),  # 太长
        ("12345678", 0),  # 纯数字
        ("非常棒的视频！", 100),  # 高赞
        ("Hello World Test", 5),  # 英文
    ]

    for text, like_count in test_cases:
        score = calculate_quality_score(text, like_count)
        display_text = text[:20] + "..." if len(text) > 20 else text
        print(f"'{display_text}' (赞:{like_count}) -> 质量分: {score}")


def test_pipeline():
    """测试完整Pipeline"""
    print("\n=== 测试完整Pipeline（阶段三） ===")

    from analysis.services import DataCleaningPipeline

    # 模拟数据
    test_texts = [
        "【視頻】這個視頻太棒了！！！！😂😂",
        "這個視頻太棒了！！！！",  # 相似
        "a",  # 太短
        "12345678",  # 垃圾
        "这是一条正常的评论",
        "另一条不同的评论",
        "这是一条正常的评论",  # 重复
        "还有一条质量不错的评论内容",
        "！！！！！",  # 垃圾
        "这条评论内容很丰富，讨论了很多有趣的话题",
    ]

    metadata = [10, 5, 0, 0, 8, 12, 3, 15, 0, 20]  # 点赞数

    # 创建Pipeline
    config = {
        'clean_for_analysis': False,
        'min_length': 2,
        'max_length': 500,
        'min_quality_score': 0.3,
        'dedup_method': 'exact',  # 使用精确去重（embedding需要模型）
    }

    pipeline = DataCleaningPipeline(config)

    # 执行Pipeline
    pipeline.add_texts(test_texts, metadata)
    pipeline.clean()
    pipeline.filter()
    pipeline.calculate_quality()
    pipeline.deduplicate()

    # 获取结果
    results = pipeline.get_results()

    print(f"\n处理结果:")
    print(f"保留 {len(results['texts'])} 条数据")
    print("\n保留的文本:")
    for i, (text, score, orig_idx) in enumerate(zip(
        results['texts'],
        results['quality_scores'],
        results['original_indices']
    ), 1):
        print(f"  {i}. [{orig_idx}] (质量:{score:.2f}) {text}")

    # 打印报告
    pipeline.print_report()


if __name__ == "__main__":
    print("=" * 60)
    print("数据清洗功能测试 - 阶段一、二、三")
    print("=" * 60)

    try:
        # 阶段一测试
        print("\n" + "=" * 60)
        print("阶段一：基础清洗")
        print("=" * 60)
        test_normalize_unicode()
        test_convert_traditional()
        test_remove_emoji()
        test_compress_repeated()
        test_clean_text()
        test_filters()

        # 阶段二测试
        print("\n" + "=" * 60)
        print("阶段二：去重和质量评分")
        print("=" * 60)
        test_dedup()
        test_quality_score()

        # 阶段三测试
        print("\n" + "=" * 60)
        print("阶段三：完整Pipeline")
        print("=" * 60)
        test_pipeline()

        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
