"""票 I-2(a)：`_qa_direct_return` 的**版本适用护栏**（先红腿 + 控制腿）。

**为什么加这道门**：QA 语料是 **Chroma 持久**的（无 TTL、重启不清、`answer_cache.clear()` 也碰不到），
而它的三条既有护栏（score / 选项指纹 / evidence 时效）**没有一条是版本判定** ⇒ 语料生成那天的法版本
会被无限期当成今天的法作答。语料生成于 2026 年（`scripts/gen_qa_corpus.py` docstring：
「智谱免费 token …（8-23 到期前消耗）」⇒ 生成日 ≤ 2026-08-23），其答案反映**民法典时代**的法
⇒ 请求的 `law_as_of` 若落在分水岭之前，直返就是**用后法答前事**。

**判据放在单元级**：本票给 `_qa_direct_return` 加的是**第四**条护栏（票面 I-4 明令不动前三条），
函数签名与调用点语义清楚，单元级即可钉死。真实链路的读数另有：语料标注前后的计数见
`dispatch-output/hij-i-20260920/`。

⚠️ 本轮只做**不需要 Owner 放行**的代码面；**语料写标注**是单独一步（写前逐条备份、写后给前后计数）。
"""

import inspect
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402

ANSWER = "（预生成解析答案）试用期最长六个月。"
BASIS = "2026-08-23"  # 语料标注的版本基准日（生成日上界）
POST = date(2026, 9, 20)  # 分水岭之后的请求基准日
PRE = date(2019, 5, 1)  # 分水岭之前的请求基准日
_SIG = inspect.signature(main._qa_direct_return)


def _call(pre: dict, law_as_of: date | None) -> str | None:
    """按**当前**签名调用。

    为什么要探测（而不是直接传两个参数）：本文件要能跑在**改前树**上取先红读数，而票 I-2 之前
    `_qa_direct_return` 只有 1 个形参 —— 直接传两个参数会让 5 条用例**全部**红成
    `TypeError: takes 1 positional argument but 2 were given`，而票面 §0 判据 1 明确**不接受**
    把 TypeError 当作缺功能的证据（那是"红错了原因"）。
    用签名探测后：改前树上**只有先红腿**红、且红在"没拦住"这个功能点上；控制腿两侧都绿。
    """
    if len(_SIG.parameters) >= 2:
        return main._qa_direct_return(pre, law_as_of)
    return main._qa_direct_return(pre)


def _pre(basis: str | None = BASIS) -> dict:
    """构造一个"三道既有护栏全过"的 `pre`：只留版本护栏这一条变量。"""
    qa = {"score": 0.95, "answer": ANSWER, "evidence": "", "question": "试用期最长多久"}
    if basis is not None:
        qa["law_as_of_basis"] = basis
    return {"qa_hit": qa, "rewritten": "试用期最长多久", "conv_id": 1}


def test_control_same_side_of_watershed_still_direct_returns():
    """控制腿（必须两侧都绿）：请求基准日在分水岭**之后** ⇒ 照常直返，零 token 特性保住。"""
    assert _call(_pre(), POST) == ANSWER


def test_control_missing_law_as_of_still_direct_returns():
    """控制腿：调用方**没给**基准日（None）⇒ 不拦（保持旧行为，不因缺参数扩大拦截面）。"""
    assert _call(_pre(), None) == ANSWER


def test_control_unlabelled_record_still_direct_returns():
    """控制腿：语料**没有**基准日字段 ⇒ 不拦（这道门的射程只覆盖"已标注"的记录）。"""
    assert _call(_pre(basis=None), PRE) == ANSWER


def test_control_dirty_basis_value_does_not_widen_blocking():
    """控制腿：基准日是脏值（解析不了）⇒ 不拦（不把"不认识"当成"冲突"）。"""
    assert _call(_pre(basis="not-a-date"), PRE) == ANSWER


def test_pre_watershed_request_misses_the_labelled_record():
    """先红腿：请求基准日在分水岭**之前**，而语料基准日在之后 ⇒ 必须 miss（回落 LLM）。

    改前形态：`_qa_direct_return` 只看 score/指纹/evidence 时效 ⇒ 这里会**直接返回预生成答案**，
    即"用民法典答 2019 年的事"。
    """
    assert _call(_pre(), PRE) is None
