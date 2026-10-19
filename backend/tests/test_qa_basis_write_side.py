"""写侧版本基准日（先红）：QA 写入路径必须自带 `law_as_of_basis`。

**缺口（独立评审抓出，我自己复量确认）**：全仓**没有任何生产者**写 `law_as_of_basis`——
`add_qa_pair` 的 metadata 只有 `answer/evidence/origin/options_fingerprint` 四个键，
而四条写路径全过它（`qa_seeds` / `scripts/gen_qa_corpus.py` / `create_candidate` 自动收录 /
`decide_candidate` 人工采纳）。存量 279 条的值来自 09-20 一次性回填
（`gate_exit_registry.py` 记着 `law_as_of_basis_src = "inferred-docstring-8-23"`）。

⇒ 自第四轮核对把"缺 basis ⇒ 不参与生成"上线后，**新沉淀的语料永久不可能被直返或被注入 prompt**，
零模型直返这条能力会静默衰减到那 279 条。`main.py` 里"`law_as_of_basis` 只由 seeds/生成脚本写"
那句注释也是错的（那两个文件里一次都没出现过）——幽灵注释。

**修法（与票 T6 同一形状：单一真源堵整类，而不是逐点补）**：`add_qa_pair` 在调用方未给基准日时
自己落**当日（UTC 钟）**——与 `QaCandidate.created_at` 同一个钟，四条路径不再差一天。
这在四条路径上都是**真话**：
`_post` 的沉淀闸明令"带历史基准日的请求不沉淀" ⇒ 经它进来的答案本来就是按当日法律产出的；
种子与生成脚本也是按当日法律现生成。唯一需要单独对待的是**人工采纳**：答案可能是几天前产生的
⇒ `decide_candidate` 显式传候选的 `created_at` 日期，而不是采纳日。

判据（5 条 = 1 先红 + 3 控制 + 1 生产路径）：
  ① 先红：不给基准日 ⇒ 存当日（改前存 ""）；
  ② 控制：显式传入 ⇒ 原样保留（不覆盖调用方给的版本）；
  ③ 控制：写入后按读侧真判据 `qa_provenance_verifiable` 判为**可校验**（端到端，不只验字段）；
  ④ 控制：采纳路径存的是**候选产生日**而不是今天；
  ⑤ 生产路径：人工采纳 `decide_candidate` ⇒ 落库记录带 basis 且真判据放行（W06-P0：原为 `create_candidate` 自动收录）。

⚠️ 题面必须各用例唯一：本文件的定位方式是按题干文本取记录（与 T6 同法），同题面写两次会串。
"""

import os
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
from models import QaCandidate  # noqa: E402
from retrieval_core import qa_provenance_verifiable  # noqa: E402

CAND_DATE = "2026-09-01"  # 刻意不等于钉住的"当日"，否则腿 ④ 测不出"采纳日 vs 产生日"
PINNED_TODAY = "2026-09-25"  # = _PinnedDatetime 的 UTC 日期


class _PinnedDatetime:
    """钉住写侧时钟：默认基准日取 **UTC 当日**（与 `QaCandidate.created_at` 同一个钟）。

    为什么不拿 `date.today()` 当期望值去比对：本机是 UTC+8，写这条判据时恰好跨过本地午夜
    （本地 09-25 / UTC 09-24），期望值会跟着宿主环境漂，跨午夜还会自己抖。钉死后
    「用哪个钟」这条决策本身也被断言守住了——改成走 `date.today()` 就撞不上期望值。
    """

    @staticmethod
    def now(tz=None):
        assert tz is UTC, "写侧基准日必须走 UTC 钟（与 created_at 同）"
        return datetime(2026, 9, 25, 1, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _pin_write_clock(monkeypatch):
    monkeypatch.setattr(ks, "datetime", _PinnedDatetime)


def _stored(question: str) -> dict:
    data = ks._qa_store._collection.get(include=["documents", "metadatas"])
    for doc, meta in zip(data.get("documents") or [], data.get("metadatas") or [], strict=False):
        if (doc or "").strip() == question.strip():
            return meta or {}
    raise AssertionError(f"未找到刚写入的 QA 记录：{question[:30]}")


def test_add_qa_pair_stores_basis_when_absent(double_embeddings):
    """先红：调用方不给基准日时，`add_qa_pair` 必须自己落当日（改前根本没人写这个键）。"""
    q = "写侧基准日先红腿：用人单位能否随意约定试用期？"
    ks.add_qa_pair(q, "不得随意约定", evidence="劳动合同法|第十九条")
    assert str(_stored(q).get("law_as_of_basis") or "") == PINNED_TODAY


def test_control_explicit_basis_is_preserved(double_embeddings):
    """控制腿：显式传入的基准日原样保留（调用方知道的版本比默认值可信）。"""
    q = "写侧基准日控制腿：保证方式未约定时按哪种处理？"
    ks.add_qa_pair(q, "一般保证", evidence="民法典|第六百八十六条", basis="2019-06-06")
    assert str(_stored(q).get("law_as_of_basis") or "") == "2019-06-06"


def test_control_written_record_passes_the_real_provenance_gate(double_embeddings):
    """控制腿（端到端）：写入后的记录必须能过**读侧真判据**，否则写侧补了也白补。

    只断言"键存在且非空"不够——判据还看 `evidence` 形状，两条得一起成立。
    """
    q = "写侧判据端到端腿：借款合同的利息约定不明如何处理？"
    ks.add_qa_pair(q, "视为没有利息", evidence="民法典|第六百八十条")
    meta = _stored(q)
    qa_hit = {
        "answer": meta.get("answer", ""),
        "evidence": meta.get("evidence", ""),
        "law_as_of_basis": meta.get("law_as_of_basis", ""),
        "fingerprint": meta.get("options_fingerprint", ""),
    }
    assert qa_provenance_verifiable(qa_hit) is True


def test_control_adoption_stores_candidate_date_not_today(double_embeddings):
    """控制腿：人工采纳存的是**候选产生日**，不是采纳那一刻的今天。

    答案的法律版本身份来自它被产出的那天；隔了 20 天采纳不会让它变成今天的法。
    """
    q = "写侧采纳日期腿：劳动者提前多少日通知可以解除劳动合同？"
    cand = QaCandidate(
        id=991,
        question=q,
        answer="提前三十日以书面形式通知",
        grounded_score=0.5,
        evidence="劳动合同法|第三十七条",
        status="pending",
        created_at=datetime(2026, 9, 1, 3, 0, 0),
    )
    db = MagicMock()
    db.get.return_value = cand
    ks.decide_candidate(db, 991, "approved")
    stored = str(_stored(q).get("law_as_of_basis") or "")
    assert stored == CAND_DATE
    assert stored != PINNED_TODAY, "存成了采纳日 ⇒ 答案的法律版本身份被改写"


def test_human_approve_path_stores_basis(db, double_embeddings):
    """生产路径（W06-P0 换契约）：人工采纳 ⇒ 落库记录带 basis（采纳用候选 `created_at` 当日口径），过读侧真判据。

    W06-P0 前这里是「有据分 ≥0.89 自动收录」腿；新契约下 create_candidate 一律 pending、不写向量 ⇒
    触发点改到人工采纳 decide_candidate(approved)，判据逐字保留（basis 仍等于钉住的当日）。
    """
    q = "写侧自动收录腿：用人单位可以扣工资作为违约金吗？"
    row = ks.create_candidate(db, q, "一般不可以", 0.95, "劳动合同法|第九十条")
    # 产生日刻意取 CAND_DATE（≠ PINNED_TODAY）⇒ 本腿**自己能分辨**「取产生日」还是「取今天」，
    # 不再依赖同文件 109 行控制腿兜底（独立 review 指出原钉法判别力被削弱）。
    row.created_at = datetime(2026, 9, 1, 1, 0, 0)
    db.commit()
    ks.decide_candidate(db, row.id, "approved")
    meta = _stored(q)
    stored = str(meta.get("law_as_of_basis") or "")
    assert stored == CAND_DATE, f"人工采纳应存候选产生日：{stored}"
    assert stored != PINNED_TODAY, "存成了采纳日/今天 ⇒ 答案的法律版本身份被改写"
    assert (
        qa_provenance_verifiable(
            {
                "answer": meta.get("answer", ""),
                "evidence": meta.get("evidence", ""),
                "law_as_of_basis": meta.get("law_as_of_basis", ""),
            }
        )
        is True
    )
