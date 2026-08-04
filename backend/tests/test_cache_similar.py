"""缓存近重复命中测试（grilling 定稿）：结构护栏 + get_similar 余弦命中。

护栏三件套（确定性纯函数）：极性（防否定词盲区）/选项数/标号体系（防"选B"错位展示给 ①-④ 题）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


import answer_cache
import retrieval_core as rc
from query_understand import _label_system, _polarity, option_count


def _v(*xs):
    """小向量（模拟嵌入）。"""
    return list(xs)


# ---------------- 护栏纯函数 ----------------
def test_polarity():
    assert _polarity("下列说法正确的是？A.甲") == "true"
    assert _polarity("下列说法不正确的是？A.甲") == "false"  # 先匹配"不正确"
    assert _polarity("下列哪项是错误的？A.甲") == "false"
    assert _polarity("请分析以下案情。") == ""  # 中性
    # 选项内容含"错误"不干扰题干极性（只在题干段判定）
    assert _polarity("下列说法正确的是？A.甲不承担错误责任") == "true"


def test_label_system():
    assert _label_system("A.甲 B.乙") == "A-D"
    assert _label_system("Ａ：甲 Ｂ：乙") == "A-D"
    assert _label_system("①甲 ②乙") == "circ"
    assert _label_system("1.甲 2.乙") == "num"
    assert _label_system("这是一个普通问题") == "none"


def test_option_count():
    assert option_count("A.甲 B.乙 C.丙 D.丁") == 4
    assert option_count("①甲 ②乙 ③丙") == 3
    assert option_count("1.甲 2.乙 3.丙 4.丁 5.戊") == 5
    assert option_count("普通问题") == 0


# ---------------- get_similar ----------------
def _put(key, text_vec, pol="", cnt=0, lab="", answer="缓存答案"):
    answer_cache.put(
        key, answer, [{"source": "民法典", "article": "第一千一百六十五条"}],
        embedding=text_vec, polarity=pol, option_count=cnt, label_system=lab,
        model="qwen3.7-plus",
    )


def test_get_similar_hits_when_guards_match():
    answer_cache.clear()
    _put("k1", _v(1, 0, 0), pol="true", cnt=4, lab="A-D")
    hit = answer_cache.get_similar(
        _v(0.99, 0.1, 0), polarity="true", option_count=4, label_system="A-D",
    )
    assert hit is not None and hit["answer"] == "缓存答案"


def test_get_similar_polarity_mismatch_misses():
    answer_cache.clear()
    _put("k1", _v(1, 0, 0), pol="true", cnt=4, lab="A-D")
    # 同嵌入但极性不同（"正确的是" vs "不正确的是"）→ 必须 miss（防否定词盲区）
    assert answer_cache.get_similar(
        _v(0.99, 0.1, 0), polarity="false", option_count=4, label_system="A-D",
    ) is None


def test_get_similar_option_count_mismatch_misses():
    answer_cache.clear()
    _put("k1", _v(1, 0, 0), pol="true", cnt=4, lab="A-D")
    assert answer_cache.get_similar(
        _v(0.99, 0.1, 0), polarity="true", option_count=5, label_system="A-D",
    ) is None


def test_get_similar_label_system_mismatch_misses():
    answer_cache.clear()
    _put("k1", _v(1, 0, 0), pol="true", cnt=4, lab="A-D")
    assert answer_cache.get_similar(
        _v(0.99, 0.1, 0), polarity="true", option_count=4, label_system="circ",
    ) is None


def test_get_similar_below_threshold_misses():
    answer_cache.clear()
    _put("k1", _v(1, 0, 0), pol="true", cnt=4, lab="A-D")
    # 余弦 ≈ 0.63 < 0.95 → miss
    assert answer_cache.get_similar(
        _v(0.8, 1, 0), polarity="true", option_count=4, label_system="A-D",
    ) is None


def test_get_similar_no_embedding_entry_skipped():
    answer_cache.clear()
    answer_cache.put("k_legacy", "旧答案", [{"source": "民法典", "article": "第一千一百六十五条"}])  # 无 embedding
    assert answer_cache.get_similar(
        _v(1, 0, 0), polarity="", option_count=0, label_system="none",
    ) is None
