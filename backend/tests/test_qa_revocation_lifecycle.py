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
from pathlib import Path

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


def test_reject_stops_both_read_exits_without_deleting_the_record(db, double_embeddings, monkeypatch):
    """W06-IMPL 改写（原钉 ①：SQL 说 rejected，两条出口仍服务）：

    现钉新契约——拒绝后两条语料出口都 miss，但向量记录**照旧在服务侧读得回**（形状 P「隔离不删」：
    只置资格、不删数据）。仍**保留**：status=rejected、search_qa 命中、answer 不变（这些今天也成立）。
    """
    q = "撤回生命周期甲：试用期的约定有什么上限？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)  # 机器自动收录
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])

    ks.decide_candidate(db, row.id, "rejected")
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "rejected"
    # 新契约的资格位：拒绝 = 置 revoked（不是删行、不是删向量）
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().eligibility == "revoked"

    hit = ks.search_qa(q)
    assert hit is not None, "读侧根本没命中 ⇒ 后面的断言全部失去对象（本条判据空转）"
    assert hit["answer"] == ANSWER
    assert hit["qa_candidate_id"] == row.id, "向量链没闭合 ⇒ 出口无从核验状态"

    # 原钉：`== ANSWER`（直返仍服务）⇒ 现钉：miss（读出口自判 revoked）
    assert main._qa_direct_return({"rewritten": q, "qa_hit": hit}) is None
    prompt = _prompt_text(main._build_messages(_pre(q, hit)))
    # 原钉：`ANSWER in prompt` / `"此前已确认的问答" in prompt`（注入仍发生）⇒ 现钉：都不出现
    assert ANSWER not in prompt
    assert "此前已确认的问答" not in prompt


def test_revocation_is_visible_in_sql_at_the_moment_of_invalidate(db, double_embeddings, monkeypatch):
    """票 W06-FIX V1（F5）：撤回必须**提交可见之后**才清缓存——并发判据，不是「你按顺序调了吗」的断言。

    失效形状（改前现量）：`decide_candidate` 拒绝分支是 `invalidate()` → `commit()`。
    在 invalidate 之后、commit 之前那一段里，**并发请求**仍从 SQL 读到旧资格 `ok`，
    于是它把刚被撤掉的答案**写回回答缓存**（TTL 6 小时，`main.py` 的两处 `answer_cache.put`），
    「撤回即时生效」在这个窗口里被反向击穿；SQLite 单写者 + `timeout=30` 只会把窗口拉长。

    判据怎么把「并发」跑出来（可控钩子，不是顺序断言）：
    把 `retrieval.invalidate` 换成一只**并发读者替身**——它在缓存被清的那一刻
    ① 另开一条 session 读同一行的 `eligibility`（=另一个请求能看到的状态），
    ② 用**生产判据** `qa_eligibility.evaluate_revocation_state` 判这条语料还能不能被服务，
    ③ 若判据放行就**按生产写法把答案 put 回缓存**（这就是事故本身，不是它的比喻）。
    三条断言分别钉住这三步；改前 ①读到 `ok`、②放行、③缓存里重新出现已撤回答案 ⇒ 三条全红。
    顺序断言（「invalidate 的调用序号在 commit 之后」）在本文件里**不作为判据**：
    它换一种写法（先 flush 再 commit、或把 invalidate 塞进 commit 事件）就能绕过，而并发窗口照旧。
    """
    import answer_cache
    import database
    import models
    import qa_eligibility as qe

    q = "撤回并发判据：缓存被清的那一刻，另一个请求读到的是什么资格？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    hit = ks.search_qa(q)
    assert hit is not None and hit["qa_candidate_id"] == row.id, "链没闭合 ⇒ 并发读者无从判状态"

    cache_key = answer_cache.make_key(q, "legal_query", "2026-08-23", ["劳动合同法|第十九条"])
    answer_cache.put(cache_key, ANSWER, [])
    assert answer_cache.get(cache_key) is not None, "预置的缓存条目没写进去 ⇒ 下面三条断言失去对象"

    seen: dict[str, object] = {}
    real_invalidate = retrieval.invalidate

    def concurrent_reader_invalidate():
        """站在 invalidate 那一刻的第二个请求：读 SQL → 跑生产判据 → 按判据决定是否写回缓存。"""
        probe = database.SessionLocal()
        try:
            r = probe.get(models.QaCandidate, row.id)
            seen["eligibility"] = None if r is None else r.eligibility
        finally:
            probe.close()
        seen["predicate_allows"] = qe.evaluate_revocation_state(hit).allow
        if seen["predicate_allows"]:
            answer_cache.put(cache_key, ANSWER, [])  # 事故本体：已撤回的答案被写回缓存
        real_invalidate()

    monkeypatch.setattr(retrieval, "invalidate", concurrent_reader_invalidate)
    ks.decide_candidate(db, row.id, "rejected")

    assert seen, "钩子根本没被调用 ⇒ 本条判据空转（先查写序改动是否把 invalidate 删了）"
    assert seen["eligibility"] == "revoked", (
        f"invalidate 时并发请求读到的仍是 {seen['eligibility']!r} ⇒ 撤回还没提交可见，"
        "窗口内的并发请求会把已撤回答案写回缓存（票 W06-FIX F5 的失效形状）"
    )
    assert seen["predicate_allows"] is False, "生产判据在 invalidate 那一刻仍放行 ⇒ 缓存清完又会被填回去"
    assert answer_cache.get(cache_key) is None, "已撤回的答案重新出现在回答缓存里 ⇒ TTL 内继续零 token 直返"


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
    """③ QA 侧没有删除入口：按 **AST 全仓穷举**（backend 下除 tests 之外的每一只 .py）。

    为什么不是只扫 `knowledge_service` 一只文件：独立复核指出——只在一只文件里穷举时，
    在 `main.py` 加一句 `ks._qa_store.delete(...)` 本条仍会绿，那是"没有 X"最坏的假阴性形状。
    现在按 `ast.unparse(node.value).endswith("_qa_store")` 收属性访问，点号别名形式（`ks._qa_store.X`）
    也能撞到。
    正对照（同一台机器现量）：全仓 `delete/deletes` 调用 14 处、QA 侧 0 处——
    没有这半条，"0 处"会因为"扫描器根本没在找东西"而恒真。

    第二半把"确实存在 delete"钉在**条文库**那一侧：两处 delete 的接受者必须逐字是 `_collection()`
    （knowledge_service.py:55 绑的是 `vectorstore`，不是 QA 集合）。
    """
    root = Path(__file__).resolve().parents[1]
    accessed, qa_deletes, total_deletes = set(), [], 0
    for py in sorted(root.rglob("*.py")):
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and ast.unparse(node.value).endswith("_qa_store"):
                accessed.add(node.attr)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr
                in (
                    "delete",
                    "deletes",
                )
            ):
                total_deletes += 1
                if "_qa_store" in ast.unparse(node.func.value):
                    qa_deletes.append(f"{py.name}:{node.lineno}")
    assert accessed == {"_collection", "add_documents", "similarity_search_with_score"}, sorted(accessed)
    assert qa_deletes == [], qa_deletes
    assert total_deletes >= 10, f"全仓 delete 调用只数到 {total_deletes} 条 ⇒ 扫描器打空了，本条不可信"

    tree = ast.parse(inspect.getsource(ks))
    receivers = sorted(
        {
            ast.unparse(c.func.value)
            for c in ast.walk(tree)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("delete", "deletes")
        }
    )
    assert receivers == ["_collection()"], f"条文库/QA 两侧的 delete 接受者形状变了（现量 {receivers}）"
    # 功能面的同一件事在第①条里已经跑过：拒绝之后 QA 记录仍在（不删），但三条出口都不再服务它。


def test_reject_and_auto_approve_both_invalidate_the_answer_cache(db, double_embeddings, monkeypatch):
    """W06-IMPL 改写（原钉「拒绝路径不碰回答缓存」的漏口）：

    票面 :350 点名「已写 QA、**回答缓存**及进程缓存」要一起失效——此前拒绝分支一个都不碰（少一份拷贝）。
    现钉新契约：`decide_candidate` 拒绝分支也调 `retrieval.invalidate()`，而 invalidate 内部延迟 import
    `answer_cache` 一起清（retrieval.py:765-781），⇒ 这条问句在 TTL 内已落进回答缓存的那份答案
    **会因为拒绝而消失**——`main.py:2193` 的 `answer_cache.get(cache_key)` 那道出口随之 miss。
    """
    import answer_cache
    import retrieval

    # 先取**原件**源码：一旦下面把 `retrieval.invalidate` 换成替身，`inspect.getsource` 读到的就是
    # 我这条测试里的 lambda（本条第一版就是这么红的）。判据要看的是生产函数，不是我的替身。
    invalidate_src = inspect.getsource(retrieval.invalidate)
    assert "answer_cache" in invalidate_src, "invalidate 不再连带清回答缓存 ⇒ 下面那句因果推理失去依据"

    calls: list[str] = []
    real_invalidate = retrieval.invalidate  # 替身装好之前先把**原件**留住（下面那条真判据要用它）
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    q = "撤回生命周期庚：自动收录后又被拒绝，回答缓存会跟着失效吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert calls == ["invalidate"], "自动收录那一步本来就该清一次缓存；它不清的话本条失去对照基准"

    calls.clear()
    ks.decide_candidate(db, row.id, "rejected")
    # 原钉 `calls == []`（拒绝不碰回答缓存 = 第三份漏口）⇒ 现钉 `["invalidate"]`：
    # 拒绝走形状 B，必须调 invalidate 连带清回答缓存（§4 项 1 的第三条出口）。本条原注释就要求这样改写、不删。
    assert calls == ["invalidate"], "拒绝路径没清缓存 ⇒ §4 项 1 的回答缓存出口仍会命中旧答案"

    # 票 W06-FIX F9/V8：**原钉 `assert hasattr(answer_cache, "get")` ⇒ 现钉真判据，理由：恒真**。
    # `answer_cache` 是个模块对象，`hasattr(..., "get")` 在这个模块存在的任何一秒都是 True
    # （模块连不上读侧入口的情况本仓没有发生过，也不会由这条断言发现）——
    # 「回答缓存的读侧入口确实存在」这句话要用**行为**判，不是用**属性名存在**判。
    # 现钉：真的写进缓存 ⇒ 真的调**原件** invalidate ⇒ 真的读不回来。
    # 这半条同时是上面那句因果的依据：invalidate 确实能清到回答缓存（不是只清检索缓存）。
    q_live = "撤回生命周期庚补：invalidate 真的能清掉回答缓存里那一条吗？"
    key = answer_cache.make_key(q_live, "legal_query", "2026-08-23", ["劳动合同法|第十九条"])
    answer_cache.put(key, ANSWER, [])
    hit = answer_cache.get(key) or {}
    assert hit.get("answer") == ANSWER, "写进去的条目读不回来 ⇒ 下面那条 invalidate 判据失去对象"
    real_invalidate()
    assert answer_cache.get(key) is None, "invalidate 没清掉回答缓存 ⇒ 拒绝路径的第三条出口仍然命中旧答案"


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


def test_r2_commit_failure_still_clears_the_cache_on_both_write_branches(db, double_embeddings, monkeypatch):
    """R2-F7（复核第二轮，本仓**上一轮自己引进**的新静默路径）：提交失败 ⇒ 向量已经写了，缓存却没清。

    `10d1dc0` 把 `invalidate()` 从 commit **之前**挪到之后（那一步是对的：并发读者要在缓存被清之前
    就读到新资格），代价是新增了一条失败路径：`db.commit()` 抛了 ⇒ 一行都不执行 ⇒
    向量里那条 QA 已经存在（`add_qa_pair` 先写），而进程缓存与回答缓存留着**旧**读数。
    改前无条件清，所以这条洞是本轮新挖的。

    现钉两支（批准/auto-approve 各一）：提交炸 ⇒ 异常照旧上抛，但 `retrieval.invalidate()` **仍被调用**。
    用调用计数器判，不用 `hasattr`（本仓已把「属性存在」类恒真判据改写过一次，见上面 V8 那条）。
    """
    import inspect

    calls: list[str] = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    def boom():
        raise RuntimeError("模拟提交失败（锁／唯一约束／进程被杀都算这一类）")

    # ── 支 1：`create_candidate` 的自动收录（≥0.89 那一支，先写向量再提交）
    q1 = "复核R2戊：自动收录提交失败时缓存清不清？"
    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        ks.create_candidate(db, q1, ANSWER, 0.95, EVIDENCE)
    assert calls == ["invalidate"], f"自动收录这一支提交失败后没清缓存（向量里已经有 {q1} 那条）：{calls}"

    # ── 支 2：`decide_candidate` 的人工采纳（同样先写向量再提交）
    calls.clear()
    monkeypatch.undo()  # 还原 db.commit／retrieval.invalidate，先把候选正常落成待审行
    row = ks.create_candidate(db, "复核R2戊补：人工采纳这一支提交失败呢？", ANSWER, 0.55, EVIDENCE)
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))
    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        ks.decide_candidate(db, row.id, "approved")
    assert calls == ["invalidate"], f"人工采纳这一支提交失败后没清缓存：{calls}"

    # 注释里那句被复核打穿的假话不许留在原地当依据（它现在**是错的**，留着比删掉更坏）
    src = inspect.getsource(ks.create_candidate) + inspect.getsource(ks.decide_candidate)
    assert "没有变更就没有该清的" not in src, "注释仍声称「提交失败就不清缓存」⇒ 那是被击穿的那句原话"


def test_r2_successful_commit_still_clears_the_cache_exactly_once(db, double_embeddings, monkeypatch):
    """R2-F7 的反对照：`try/finally` 不许把正常路改成「清两次」或「每次都清」。

    没有这条对照，上面那条判据会被一个无条件空转的 `finally` 一起骗过去（例如把 invalidate
    挪到函数最外层无条件调用 ⇒ 待审分支也清、成功分支清两遍，读数从此不能当指标）。
    """
    calls: list[str] = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    ks.create_candidate(db, "复核R2戊再补：待审分支提交成功该不该清缓存？", ANSWER, 0.55, EVIDENCE)
    assert calls == [], f"待审分支不写向量，也不该清缓存：{calls}"

    ks.create_candidate(db, "复核R2戊再补：自动收录提交成功清几次？", ANSWER, 0.95, EVIDENCE)
    assert calls == ["invalidate"], f"成功路径的清理次数漂了：{calls}"


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
