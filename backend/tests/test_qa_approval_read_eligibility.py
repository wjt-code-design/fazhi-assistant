"""W06 特征化（票面：依赖 C03，未裁前「只能特征化和设计合成迁移」）——本文件**不关任何自动功能**。

钉的是「QA 的读取资格今天到底看了什么」这一组现状事实，四条都有直接读数：

① 收录闸 `curation.should_curate(grounded, answer)` 的**签名里没有题干**（curation.py:18）
   ⇒ 结构上就不可能判「答非所问」。票面要求保留 Q 的反例：高相关分＋带引用＋长文本仍然可能
   答的是另一道题，今天照样收录。这里用题干问试用期、答案讲违约金的合成语料把它跑出来。
   ⚠️ 票面明令「不得把 grounded_top_score 改个名字就当审批正确性已修」⇒ 本文件量的不是分数名字，
   是**判定函数的输入面**。
② 自动收录（≥0.89）在 SQL 侧落 `status="approved"`（knowledge_service.py:402-428），
   而向量侧那条记录只有 `answer/evidence/origin/options_fingerprint/law_as_of_basis` 五个键
   ⇒ **没有任何字段记录"这条是谁批准的、什么时候、依据什么"**，也没有候选行的 ID，
   两份拷贝之间没有可追踪的连接。
③ 机器批准与人工批准在**两份拷贝里都长得一模一样**（都是 `approved`＋同一组 metadata 键），
   所以 `origin=qa` 的存量天然不可区分审核方式 ⇒ 管理员 DTO 也拿不出区分字段（第三条腿）。
④ 现有的资格判据确实**两个出口共用一份**（`main.py:142` 与 `request_bootstrap.py:601` 引的是同一个
   对象）——这一条是**已对称、不是缺口**，写在这里是为了防止下一轮把它当漏口再修一遍。
   真正缺的是另一根轴：两条出口的入参里都没有审批状态/SQL 会话 ⇒ 撤回无处可查（见
   `tests/test_qa_revocation_lifecycle.py`）。

**实现 W06 时应当变红的是 ①②③ 这几条**，届时请**改写**成"新契约成立"的断言，不要删掉——
删掉就等于把这块唯一的现量证据销毁了。④ 是防漂移钉子，实现前后都该一直绿。

隔离：只用 `db`（tmp_path 上的临时 SQLite）＋ `double_embeddings`（conftest 的确定性伪向量）
＋ conftest 已改写的临时 `CHROMA_DIR`。**不碰真实 `app.db`、不碰 365 MB 真实语料、不加载真权重。**
"""

import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import curation  # noqa: E402
import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import retrieval  # noqa: E402
import retrieval_core as rc  # noqa: E402
from models import QaCandidate  # noqa: E402
from retrieval_core import qa_provenance_verifiable  # noqa: E402

# 可校验引用：`rc.cited_articles` 认 JSON list[{source,article}] 形状（retrieval_core.py:91-125）
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
# 向量侧 metadata 的**全部**现量键（写侧本体 knowledge_service.py:350-363）
META_KEYS = {"answer", "evidence", "origin", "options_fingerprint", "law_as_of_basis"}
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _meta_of(question: str) -> dict:
    """按题干取回**向量侧**那条记录的 metadata（临时集合，非真实语料）。"""
    data = ks._qa_store._collection.get(include=["documents", "metadatas"])
    for doc, meta in zip(data.get("documents") or [], data.get("metadatas") or [], strict=False):
        if (doc or "").strip() == question.strip():
            return meta or {}
    raise AssertionError(f"向量侧没有这条记录：{question[:24]}")


def test_gate_signature_has_no_question_so_off_topic_answers_cannot_be_caught():
    """① 收录闸看不到题干 ⇒ 「答非所问」这类不合格答案在结构上就拦不住。"""
    assert "question" not in inspect.signature(curation.should_curate).parameters, (
        "should_curate 的输入面已经变了：本文件是特征化，变了就要一起改写"
    )
    # 票面要求保留 Q 的反例：题干问试用期，答案引的是违约金条款、带引用、够长 ⇒ 照样收录
    off_topic = (
        "根据《民法典》第五百八十五条，约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据"
        "当事人的请求予以适当减少，故本题约定的违约金应予调整。"
    )
    assert curation.should_curate(0.95, off_topic) is True
    # 控制腿：同一段文字只把引用改成不含书名号的措辞 ⇒ False。
    # 没有这条控制，上面那条绿可能来自"函数恒真"而不是"引用形状放行"，判据就空转了。
    assert curation.should_curate(0.95, off_topic.replace("《民法典》第五百八十五条", "相关违约金规则")) is False


def test_auto_approve_records_machine_source_and_closes_the_link(db, double_embeddings):
    """W06-IMPL 改写（原钉 ②：approved 但向量侧没人/没时/没 ID）：

    现钉新契约——自动收录两头都记账：SQL 侧 `approval_source="auto_by_score_inferred"`，
    向量侧 metadata 多出 `qa_candidate_id` 且与 SQL `vector_doc_id` 双向对得上。
    仍**保留**的旧事实：status=approved、记录读得回、来源可校验、答案不变（这几条今天也还成立）。
    """
    q = "自动收录特征化：用人单位与劳动者约定的试用期上限应当如何确定？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert row.status == "approved"
    assert row.approval_source == "auto_by_score_inferred", "机器批准仍不可辨识 ⇒ W06 未落地"

    meta = _meta_of(q)
    # 原钉 `set(meta) == META_KEYS`（无候选 ID）⇒ 现钉多一个 qa_candidate_id，仍逐字闭集、没放宽成 in
    assert set(meta) == META_KEYS | {"qa_candidate_id"}, f"向量侧键集变了（现量 {sorted(set(meta))}）"
    assert meta["qa_candidate_id"] == row.id, "向量侧没记回候选 ID ⇒ 双向链没闭合"

    cols = {c.name for c in QaCandidate.__table__.columns}
    # 原钉 7 列闭集 ⇒ 现钉 13 列闭集（新增 6 列逐字钉住，仍是**闭集**不是关键词筛）
    assert cols == {
        "id",
        "question",
        "answer",
        "grounded_score",
        "evidence",
        "status",
        "created_at",
        "approval_source",
        "reviewed_by",
        "reviewed_at",
        "eligibility",
        "eligibility_version",
        "vector_doc_id",
    }, sorted(cols)

    # 这条记录**不是**被既有护栏拦着的状态：读侧真判据判它"来源可校验"，两条出口都放行。
    hit = ks.search_qa(q)
    assert hit is not None, "刚写入的记录读不回来 ⇒ 后面的断言全部失去对象"
    assert qa_provenance_verifiable(hit) is True
    assert hit["answer"] == ANSWER


def test_machine_and_human_approvals_are_distinguishable_by_approval_source(db, double_embeddings):
    """W06-IMPL 改写（原钉 ③：机器批准与人工批准两份拷贝都长得一样）：

    现钉新契约——**metadata 形状**仍对两条逐字相同（都走同一个 `add_qa_pair`，只多了 qa_candidate_id），
    但 SQL 侧从此分得开：auto→`auto_by_score_inferred`（无 reviewed_at），human→`human`＋reviewed_at。
    仍**保留**：两条都 approved、metadata 键集相等、origin 都等于 "qa"、待审控制腿不变。
    """
    q_auto = "机器批准对照甲：试用期包含在劳动合同期限内吗？"
    q_human = "人工批准对照乙：用人单位可以只约定试用期而不签劳动合同吗？"

    auto_row = ks.create_candidate(db, q_auto, ANSWER, 0.95, EVIDENCE)  # ≥0.89：机器直接收录
    human_row = ks.create_candidate(db, q_human, ANSWER, 0.55, EVIDENCE)  # 待审
    assert human_row.status == "pending"
    ks.decide_candidate(db, human_row.id, "approved")  # 人工采纳

    assert auto_row.status == "approved" and human_row.status == "approved"
    # 原钉 == META_KEYS ⇒ 现钉 == META_KEYS|{qa_candidate_id}：两条 metadata 键集**仍相等**（该保留的事实），
    # 只是集合本身新增了链键——把"两条相等"这条收窄掉会销毁唯一证据，所以留着只改等号右侧。
    assert set(_meta_of(q_auto)) == set(_meta_of(q_human)) == META_KEYS | {"qa_candidate_id"}
    assert _meta_of(q_auto)["origin"] == _meta_of(q_human)["origin"] == "qa"

    # 新契约：来源可辨——这正是此前"字节级不可分"缺陷的反面（人工有 reviewed_at、机器没有）
    assert auto_row.approval_source == "auto_by_score_inferred"
    assert human_row.approval_source == "human"
    assert auto_row.reviewed_at is None and human_row.reviewed_at is not None

    # 控制腿：待审行既在 SQL 里可区分（status=pending），也没有进向量侧 ⇒
    # 上面"两条一样"不是因为"这两份拷贝里全是常数"。
    q_pending = "待审对照丙：试用期工资不得低于本单位相同岗位最低档工资的百分之多少？"
    pend = ks.create_candidate(db, q_pending, ANSWER, 0.55, EVIDENCE)
    assert pend.status == "pending"
    data = ks._qa_store._collection.get(include=["documents"])
    assert q_pending not in {str(d).strip() for d in (data.get("documents") or [])}


def test_admin_candidate_dto_exposes_no_field_to_separate_machine_from_human(db, double_embeddings):
    """③ 的另一半：审核界面 DTO 只有 `status` 一根轴 ⇒ 无法把 approved 显示成"已人工核订"（票面第六条）。"""
    q = "DTO 特征化：已采纳的候选在管理员接口里能看出是谁采纳的吗？"
    ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    rows = ks.list_candidates(db, "approved")
    assert rows, "列表读不到刚收录的候选 ⇒ 本条判据没有对象"
    keys = set(rows[0])
    assert "status" in keys
    for name in ("reviewed_by", "reviewer", "reviewed_at", "approval_source", "approved_by", "origin"):
        assert name not in keys, f"DTO 已新增 {name}：本条特征化要改写成新契约断言"


def test_the_two_exits_already_share_one_eligibility_predicate_and_never_read_the_approval_state():
    """④ 防漂移（不是缺口）：形状判据两出口同一对象；但**入参里没有审批状态**，撤回无处可查。

    `tests/test_qa_citation_gate_symmetry.py` 已钉时效判据的同一性，本条只补形状判据那一半，
    并把"两出口都不看 SQL 状态"这件事钉成一条可红的断言——W06 若要接撤回，改的是**加输入**，
    不是"再抄一份判据"。
    """
    assert main.qa_provenance_verifiable is rc.qa_provenance_verifiable
    assert main.qa_citations_in_kb is retrieval.qa_citations_in_kb

    for fn in (main._qa_direct_return, main._build_messages):
        # 闭集而不是"名字里不许出现 db/session/candidate"（独立复核打出来的）：
        # 加一个 `eligibility` 参数就把"出口不看审批状态"这件事证伪了，而旧断言会照样绿。
        expected = {"pre", "law_as_of"} if fn is main._qa_direct_return else {"pre"}
        assert set(inspect.signature(fn).parameters) == expected, (
            fn.__name__,
            sorted(set(inspect.signature(fn).parameters)),
        )
