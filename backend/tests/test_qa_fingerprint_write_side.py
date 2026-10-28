"""票 T6 写侧指纹（先红）：QA 写入路径必须自带 `options_fingerprint`。

**缺口（T6 清点 + 我复核扩大一格）**：全仓只有 `scripts/gen_qa_corpus.py:178` 传指纹；
其余三处都不传——而其中两处是**生产运行时路径**：
  · `create_candidate`（有据分 ≥0.89 自动收录）
  · `decide_candidate`（人工采纳候选）
  · `qa_seeds`（种子导入）
⇒ 经它们进来的新语料对 C4「同题干换选项」护栏是**盲的**（`stored_fp` 空 ⇒ 护栏条件
`q_fp and stored_fp and 不等` 恒不成立）。T7 补采只覆盖了存量 279 条，**没有堵住写侧**。

**修法（单一真源，堵住整类缺口而非逐点补）**：`add_qa_pair` 在调用方未给指纹时
自己用**读侧同一个** `query_understand._options_fingerprint` 现算——不新增第二份提取规则；
调用方显式传入的值优先（`gen_qa_corpus` 路径逐字不变）。

判据（5 条 = 1 先红 + 3 控制 + 1 生产路径）：
  ① 先红：不给指纹 + 带选项的题 ⇒ 存量必须是现算值（改前为 ""）；
  ② 控制：无选项的题 ⇒ 存空（**不编造**指纹）；
  ③ 控制：显式传入 ⇒ 原样保留（不覆盖调用方的值）；
  ④ 控制：现算值与读侧函数逐字一致（同一个真源）；
  ⑤ 生产路径：`create_candidate`（≥阈值自动收录）落库的记录**带**指纹。
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
from query_understand import _options_fingerprint  # noqa: E402

Q_WITH_OPTIONS = (
    "关于试用期，下列说法正确的是？"
    "A.试用期最长不得超过六个月 "
    "B.同一用人单位与同一劳动者只能约定一次试用期 "
    "C.试用期不包含在劳动合同期限内 "
    "D.试用期工资不得低于本单位相同岗位最低档工资"
)
Q_NO_OPTIONS = "民法典规定普通诉讼时效是几年？"


def _stored_fp(question: str) -> str:
    """从（默认 lane 的进程私有临时库里的）qa 集合取刚写入记录的指纹。"""
    data = ks._qa_store._collection.get(include=["documents", "metadatas"])
    for doc, meta in zip(data.get("documents") or [], data.get("metadatas") or [], strict=False):
        if (doc or "").strip() == question.strip():
            return str((meta or {}).get("options_fingerprint") or "")
    raise AssertionError(f"未找到刚写入的 QA 记录：{question[:30]}")


def test_add_qa_pair_computes_fingerprint_when_absent():
    """先红：调用方不给指纹时，`add_qa_pair` 必须自己现算（改前存 ""）。"""
    ks.add_qa_pair(Q_WITH_OPTIONS, "ABD", evidence="劳动合同法|第十九条")
    assert _stored_fp(Q_WITH_OPTIONS) == _options_fingerprint(Q_WITH_OPTIONS)
    assert _stored_fp(Q_WITH_OPTIONS) != ""


def test_control_no_options_stores_empty():
    """控制腿：无选项的题 ⇒ 存空（不编造指纹）。"""
    ks.add_qa_pair(Q_NO_OPTIONS, "三年", evidence="民法典|第一百八十八条")
    assert _stored_fp(Q_NO_OPTIONS) == ""


def test_control_explicit_fingerprint_preserved():
    """控制腿：显式传入 ⇒ 原样保留（gen_qa_corpus 的路径逐字不变）。

    注意：本题面必须与其它用例**不同**——集合按题干文本定位记录，
    同一题面写两次会让本用例读到上一条（首版即踩此坑）。
    """
    q_unique = Q_WITH_OPTIONS + "（控制腿：显式传入）"
    ks.add_qa_pair(q_unique, "ABD", evidence="x", fingerprint="EXPLICIT-FP-SENTINEL")
    assert _stored_fp(q_unique) == "EXPLICIT-FP-SENTINEL"


def test_control_same_single_source_as_read_side():
    """控制腿：现算用的是读侧同一个函数（真源唯一，不新增第二份提取规则）。"""
    q = "关于保证责任，下列说法正确的是？A.一般保证享有先诉抗辩权 B.连带责任保证无先诉抗辩权"
    ks.add_qa_pair(q, "AB", evidence="民法典|第六百八十六条")
    assert _stored_fp(q) == _options_fingerprint(q)


def test_auto_curate_path_stores_fingerprint():
    """生产路径（T6 指的第一处）：有据分 ≥0.89 自动收录 ⇒ 落库记录必须带指纹。"""
    q = "关于劳动争议，下列说法正确的是？A.劳动争议需先申请劳动仲裁 B.劳动争议可以直接起诉"
    ks.create_candidate(MagicMock(), q, "A", grounded_score=0.95, evidence="劳动争议调解仲裁法|第五条")
    assert _stored_fp(q) == _options_fingerprint(q)
    assert _stored_fp(q) != ""
