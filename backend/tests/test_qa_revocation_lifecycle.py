"""W06 特征化（撤回生命周期）：**今天没有任何一条路能让一条已收录的 QA 停止被服务**。

失效模式（全部是本文件现场跑出来的现量，不是推断）：
① 自动收录（≥0.89）先写向量集合、再写 SQL 行；把 SQL 行改成 `rejected` 只动了 SQL 一份 ⇒
   两份拷贝就此各说各话，而**两条读出口都不看 SQL**（`test_qa_approval_read_eligibility.py` 第④条已钉），
   所以"拒绝了"之后：零模型直返照样返回答案，prompt 注入照样把答案递给模型。
② 生命周期里**没有 revoked 这个状态**：`decide_candidate` 只认 approved/rejected，其它一律 ValueError
   （knowledge_service.py:450-471），而行状态保持 `approved` 不动。
③ QA 侧**没有删除入口**：本文件用 AST 穷举 `knowledge_service` 里对 `_qa_store` 的全部属性访问，
   只有 `_collection` / `add_documents` / `similarity_search_with_score` 三个——没有 delete。
   （`_collection()` 那个 delete 属**条文库**（knowledge_service.py:55 绑的是 `vectorstore`），不是 QA。）
④ 写侧非原子：SQL 提交失败 ⇒ 向量记录已经落地且无人知道（孤儿）。
⑤ 采纳不幂等：同一候选采纳两次 ⇒ 向量集合里两条。

⇒ 出口条件里那句「批准/拒绝/撤回后，已写 QA、回答缓存及进程缓存的读取资格一致」现在**不成立**，
   「任何旧出口都不能继续返回已失效条目」也没有任何机制保证。
   要闭这一格必须先有 C03 的口径（审核来源/读取资格/撤回契约三问），所以本文件**只钉现状不改行为**。

隔离同上：临时 SQLite（`db`）＋ conftest 的临时 `CHROMA_DIR` ＋ `double_embeddings`；
不碰真实 `app.db`、不碰真实语料、不加载真权重。
"""

import ast
import inspect
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import retrieval  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _hits(question: str) -> int:
    """向量集合里与该题干**逐字**相同的记录条数（临时集合，非真实语料）。"""
    data = ks._qa_store._collection.get(include=["documents"])
    return sum(1 for d in (data.get("documents") or []) if str(d).strip() == question.strip())


def _kb_has_article(monkeypatch, docs):
    """把"条文还在库里"钉成给定读数：`qa_citations_in_kb` 读 `retrieval.exact_article_lookup`，
    而直返出口历史上也读过 `main` 侧同名全局 ⇒ 两处都打，避免拦截归因到进程私有空库（假红）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _pre(q: str, hit: dict) -> dict:
    """构造注入出口需要的 `pre`（形状照 `main._build_messages` 的取键，缺一个键就 KeyError）。"""
    return {
        "intent": "legal_query",
        "is_exam": False,
        "summary": "",
        "recent": [],
        "qa_hit": hit,
        "context": "",
        "user_text": q,
        "image": None,
    }


def _prompt_text(messages) -> str:
    out = []
    for m in messages:
        c = getattr(m, "content", m)
        out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def test_reject_after_auto_approval_leaves_both_read_exits_serving_the_answer(db, double_embeddings, monkeypatch):
    """① 撤回失败面：SQL 说 rejected，两条出口都说"可以用"——这是票面「任何旧出口都不能继续返回已失效条目」的反例。"""
    q = "撤回生命周期甲：试用期的约定有什么上限？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)  # 机器自动收录
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])

    ks.decide_candidate(db, row.id, "rejected")
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "rejected"

    hit = ks.search_qa(q)
    assert hit is not None, "读侧根本没命中 ⇒ 后面的断言全部失去对象（本条判据空转）"
    assert hit["answer"] == ANSWER
    # 出口①：零模型直返
    assert main._qa_direct_return({"rewritten": q, "qa_hit": hit}) == ANSWER
    # 出口②：prompt 注入（"此前已确认的问答（可优先参考）"）
    prompt = _prompt_text(main._build_messages(_pre(q, hit)))
    assert ANSWER in prompt
    assert "此前已确认的问答" in prompt


def test_control_a_rejected_candidate_that_was_never_auto_approved_is_not_served(db, double_embeddings):
    """① 的控制腿：分数在自动阈值**以下**时，拒绝路径确实没有任何东西可服务 ⇒
    上面那条放行来自"自动收录已经写了向量"，而不是来自"拒绝函数本身放行"。"""
    q = "撤回生命周期乙：始终停留在待审的候选会被服务吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)
    ks.decide_candidate(db, row.id, "rejected")
    assert _hits(q) == 0


def test_there_is_no_revoked_state_at_all(db, double_embeddings):
    """② 生命周期只有 pending/approved/rejected：想标"撤回"直接 ValueError，且原状态一字未动。"""
    q = "撤回生命周期丙：已收录的候选能被标成 revoked 吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    with pytest.raises(ValueError) as e:
        ks.decide_candidate(db, row.id, "revoked")
    assert "approved" in str(e.value) and "rejected" in str(e.value)
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "approved"
    assert _hits(q) == 1  # 标不成 revoked，记录照旧在


def test_no_production_path_can_delete_a_written_qa_record():
    """③ QA 侧没有删除入口：对 `_qa_store` 的属性访问按 **AST 穷举**，不是按肉眼 grep。

    为什么不用 `hasattr` 或"我找了半天没有"：那种"没有 X"的断言只覆盖我想到要去看的名字。
    这里把整只模块的语法树扫一遍，收集所有以 `_qa_store` 为接受者的属性访问；
    将来谁加了 `ks._qa_store.delete(...)`，这个集合就会多一项，本条当场变红，
    逼实现者**显式承认**"我加了 QA 删除入口"（而不是让判据悄悄过期）。

    第二半把"模块里确实存在 delete"这件事钉在**条文库**那一侧：两处 delete 的接受者必须逐字是
    `_collection()`（knowledge_service.py:55 绑的是 `vectorstore`，不是 QA 集合）。
    没有这半条，第一条断言会因为"整只模块根本没有 delete"而恒真——那是假阴性机器。
    """
    tree = ast.parse(inspect.getsource(ks))
    accessed = {
        n.attr
        for node in ast.walk(tree)
        for n in ast.walk(node)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "_qa_store"
    }
    assert accessed == {"_collection", "add_documents", "similarity_search_with_score"}, sorted(accessed)
    assert not {a for a in accessed if a in ("delete", "deletes", "update", "upsert")}

    receivers = sorted(
        {
            ast.unparse(c.func.value)
            for c in ast.walk(tree)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("delete", "deletes")
        }
    )
    assert receivers == ["_collection()"], f"条文库/QA 两侧的 delete 接受者形状变了（现量 {receivers}）"
    # 功能面的同一件事在第①条里已经跑过：拒绝之后 QA 记录仍在且仍被两条出口服务。


def test_sql_commit_failure_leaves_an_orphan_vector_record(db, double_embeddings, monkeypatch):
    """④ 写侧非原子：先写向量、后提交 SQL ⇒ 提交炸了，向量里那条已经活着，而且没人知道它是谁批准的。"""

    def boom():
        raise RuntimeError("模拟提交失败（连接锁死／唯一约束／进程被杀都算这一类）")

    q = "撤回生命周期戊：SQL 提交失败时向量侧会不会留下孤儿记录？"
    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)

    assert _hits(q) == 1, "孤儿记录没写进去 ⇒ 本条判据的对象消失（改的是写序还是写侧？先查清再动）"
    db.rollback()
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.question == q).count() == 0

    # 控制腿：待审路径（阈值以下）根本不写向量 ⇒ 孤儿只可能来自"自动收录"这一支
    q2 = "撤回生命周期戊补：待审路径提交失败会留下向量记录吗？"
    with pytest.raises(RuntimeError):
        ks.create_candidate(db, q2, ANSWER, 0.55, EVIDENCE)
    assert _hits(q2) == 0


def test_approving_the_same_candidate_twice_writes_two_vector_records(db, double_embeddings):
    """⑤ 采纳不幂等：`add_qa_pair` 每次都是 `add_documents`（无 ID、无 upsert），重复采纳就叠成两条。"""
    q = "撤回生命周期己：同一候选采纳两次，向量侧是一条还是两条？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)
    ks.decide_candidate(db, row.id, "approved")
    assert _hits(q) == 1
    ks.decide_candidate(db, row.id, "approved")
    assert _hits(q) == 2, "写侧已经改成幂等 ⇒ 本条特征化要改写成「重复采纳只有一条」"
    # SQL 侧仍只有一行 ⇒ 两份拷贝的数量也开始不一致（这就是"两个独立状态各自判 approved"）
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.question == q).count() == 1
