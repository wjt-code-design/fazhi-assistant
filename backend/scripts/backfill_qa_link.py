"""票 W06-BACKFILL：存量 QA 的分类回填工具（默认 dry-run，写要 `--apply` 且只准打副本）。

为什么这张票必须存在（票面 §0）：`06da7cc` 落了 C03=P 的判据与撤回闭合，但**存量语料一条都没被隔离**
——旧向量记录的 metadata 里没有 `qa_candidate_id`（写侧本轮才补上这条链），而判据对「无链」的形状是
「状态轴不适用 ⇒ 仍由来源/时效判定」。要让「未核订存量退出直返」真的发生，就得先按审计行分类、
把登记面补齐，并且量清楚有多少记录只能靠修订三 gate③（无链 ⇒ 不进直返候选集）才摘得掉。

三件读数（票面 §2，缺一不可）
 ① 分类计数表：`human` / `auto_by_score_inferred` / `unknown` 各几条（来自实际 SQL，不是估算）。
 ② `unknown` 名单：**只有 id ＋ grounded_score ＋ 是否有向量记录**——不打题干、不打答案、
    不打任何内容哈希（题干可能就是用户问句，与 AUTH-3「日志不落原文」同一口径）。
 ③ 迁移前 vs 迁移后的「直返候选集大小」：同一批题面逐条跑真码 `main._qa_direct_return` 数**命中条数**。
    口径钉死（Owner 复核第 1 条）：成员数＝真码返回答案的条数，不是 `search_qa` 的分数命中数；
    两条腿各报各的、差几条报几条，见 `measure_direct_return` 的返回键。

分类规则（逐字照设计卡 §5；阈值取 `knowledge_service.AUTO_CURATE_THRESHOLD` 这一份真源，本票不自带第二份）
 · `status=approved` 且有 `audit_logs` 行 `action='qa.approved'` 且 `target=str(id)` 且 `admin_id` 非空 ⇒ `human`；
 · `status=approved` 且 `grounded_score >= 阈值` 且无审计行 ⇒ `auto_by_score_inferred`
   （**标 inferred 不标 proven**——`audit.py` 的审计是 best-effort，人工批准也可能没留行）；
 · 其余 ⇒ `unknown`（分数不够自动阈值却已批准、又无人工痕迹）。
 · `admin_id` 为 NULL 的审计行**不构成** human 的证据（「human 需要可证审批人」的负控）。

配对规则（票面 §3 A3：宁可留 unknown 也不猜）
 只按 `(question, answer)` **逐字相等**配对；不做任何归一化、模糊、相似度或前缀匹配；配不上 ⇒ `unknown`。

红线（票面 §1，违反任何一条就是本票失败）
 · 真实库 `backend/app.db` 与真实向量目录 `backend/chroma_db/` **只读**：DB 用
   `sqlite3.connect("file:...?mode=ro", uri=True)`；向量目录**只按只读 SQL 读元数据**，不经 chroma 客户端
   （chroma 一打开就可能在同目录建 `-wal` 或跑自己的 migration ⇒ 那就不是只读）。
 · 本脚本**对向量目录只读**：不删、不改、**不给任何向量记录写 metadata**。设计卡 §5 的「孤儿登记、
   重复标 superseded」全部落在 SQL 侧。因此**状态轴对这些存量记录不适用**——存量无链记录退出直返
   靠修订三 gate③（`qa_eligibility` 的生产面，另派），不靠本脚本。这条限制写在这里而不是藏在代码里。
 · 写只在显式 `--apply` / `--restore` 时发生；`--measure-direct-return` 也会写（import `main` 会跑
   `init_db()` ⇒ 给副本补列），所以三种模式共用同一道守卫：命中受保护路径就**动手之前**非零退出。
 · 本脚本不产生任何新的结构化日志键（只 print），所以不需要动 `observability._ACCOUNT_FIELDS`。

用法
 只读读数（默认真库路径，不写一个字节）：python scripts/backfill_qa_link.py --json-out <path>
 副本上真回填：            python scripts/backfill_qa_link.py --apply --db <副本 app.db> --chroma <副本 chroma_db> --snapshot <path>
 直返候选集读数（副本）：  python scripts/backfill_qa_link.py --measure-direct-return --db <副本> --chroma <副本> --questions <题集> --json-out <path>
 按快照回退（A5）：         python scripts/backfill_qa_link.py --restore --db <副本> --snapshot <path>
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 分类词汇（设计卡 §5 的原话；`auto_by_score_inferred` 不许写成 `proven`）
HUMAN = "human"
AUTO_INFERRED = "auto_by_score_inferred"
UNKNOWN = "unknown"
NOT_APPROVED = "not_approved"

# 审计行的拼法：**代码**写的是 `qa.approved`（`main.py` 的 `log_audit(_admin.id, f"qa.{decision}", target=cand_id)`），
# `models.py` 注释举例写 `qa.approve` —— 那是幽灵注释，过滤必须按代码这一份。
QA_APPROVED_ACTION = "qa.approved"

# 受保护路径的**形状**（票面 §1 红线表）：按「目录名＋文件名」判，主仓与候选工作树两套树一起拦住。
_PROTECTED_DB_PARENT = "backend"
_PROTECTED_DB_NAME = "app.db"
_PROTECTED_CHROMA_DIRNAME = "chroma_db"

DEFAULT_DB = BACKEND_DIR / "app.db"
DEFAULT_CHROMA = BACKEND_DIR / "chroma_db"

# 本脚本允许改写的 SQL 列（资格列＋status）。**不含** question/answer/grounded_score/evidence：
# 改正文等于改语料内容，本票只分类不修词。
_WRITABLE_COLUMNS = ("status", "approval_source", "reviewed_by", "reviewed_at", "eligibility", "vector_doc_id")


class RefusalError(RuntimeError):
    """守卫拒绝：命中受保护路径，或写模式缺显式目标。抛出来，动手之前就停。"""


# ==================== 红线守卫 ====================
def protected_targets(db_path: str | None, chroma_path: str | None) -> list[str]:
    """返回命中的受保护目标（空列表＝不是真实路径）。纯字符串判定，不碰文件系统、不开任何句柄。

    两条腿都要，少一条这张票就不可执行：
     · **形状腿**：票面 §1 那张表写的是 `backend/app.db` 与 `backend/chroma_db` —— 按「父目录名＋自身名」
       这一对判，主仓与候选工作树两套树一起拦住。
       为什么不能只按「路径里出现过 chroma_db 这个名字」判：副本目录本来就该叫 `chroma_db`
       （chroma 的 persist 目录形状如此），一刀切会把**所有副本**也拦掉 ⇒ `--apply` 在这台机器上
       变成永远不可执行，读数③/A5 就没有真跑过的那条腿。这一格由
       `tests/test_backfill_qa_link.py::test_a6_refuses_the_live_default_paths_of_this_tree`
       与 `test_a6_allows_a_copy_that_keeps_the_production_dir_name` 一红一绿钉住。
     · **真身腿**：与两只 live 默认路径（本树的 `backend/app.db`、`backend/chroma_db`）比 realpath，
       改名也躲不掉。
    """
    hits: list[str] = []
    for kind, raw in (("db", db_path), ("chroma", chroma_path)):
        if not raw:
            continue
        p = Path(raw)
        name = p.name.lower()
        parent = p.parent.name.lower()
        if kind == "db" and name == _PROTECTED_DB_NAME and parent == _PROTECTED_DB_PARENT:
            hits.append(f"{kind}={p}")
        elif kind == "chroma" and name == _PROTECTED_CHROMA_DIRNAME and parent == _PROTECTED_DB_PARENT:
            hits.append(f"{kind}={p}")
    # 真身腿：与两只 live 默认路径同指一处也算真实路径（resolve 比，防 8.3 短名/链接绕过）
    for kind, raw, live in (("db", db_path, DEFAULT_DB), ("chroma", chroma_path, DEFAULT_CHROMA)):
        if raw and str(Path(raw).resolve()) == str(Path(live).resolve()):
            tag = f"{kind}={Path(raw)}"
            if tag not in hits:
                hits.append(tag)
    return hits


def assert_not_real_targets(db_path: str | None, chroma_path: str | None, mode: str) -> None:
    """所有会写的模式（`--apply`／`--restore`／`--measure-direct-return`）在动手之前过这道门（A6）。"""
    hits = protected_targets(db_path, chroma_path)
    if hits:
        raise RefusalError(
            f"[backfill_qa_link:{mode}] 拒绝执行：目标是真实库/真实向量目录，本轮不碰生产"
            f"（票面 §1 红线表；对真库执行需要 Owner 单独授权）：{'；'.join(hits)}"
        )


def require_explicit_targets(db_path: str | None, chroma_path: str | None, mode: str) -> tuple[Path, Path]:
    """写模式两个目标都必须显式给出（缺一个就可能默认落到真实路径 ⇒ 一律拒）。"""
    if not db_path or not chroma_path:
        raise RefusalError(f"[backfill_qa_link:{mode}] 拒绝执行：必须同时显式给出 --db 与 --chroma（指向副本）。")
    return Path(db_path).resolve(), Path(chroma_path).resolve()


# ==================== 只读读取 ====================
def connect_read_only(db_path: Path | str) -> sqlite3.Connection:
    """真实库/副本统一的只读打开方式（票面 §1 逐字要求的 uri＋mode=ro 形状）。"""
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("select name from sqlite_master where type='table'")}


def read_candidates(con: sqlite3.Connection) -> list[dict[str, Any]]:
    """`qa_candidates` 全部行。**按现有列读**：未迁移的真库没有资格六列，缺的键取 None 而不是炸。"""
    cols = table_columns(con, "qa_candidates")
    if "id" not in cols:
        return []
    wanted = [
        c
        for c in (
            "id",
            "question",
            "answer",
            "grounded_score",
            "evidence",
            "status",
            "approval_source",
            "reviewed_by",
            "reviewed_at",
            "eligibility",
            "eligibility_version",
            "vector_doc_id",
        )
        if c in cols
    ]
    rows = con.execute(f"select {', '.join(wanted)} from qa_candidates order by id").fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = {k: r[k] for k in wanted}
        for k in (
            "approval_source",
            "reviewed_by",
            "reviewed_at",
            "eligibility",
            "eligibility_version",
            "vector_doc_id",
        ):
            d.setdefault(k, None)
        out.append(d)
    return out


def read_known_admin_ids(con: sqlite3.Connection) -> set[int]:
    """在册管理员 id：用来报「审计行的 admin_id 指不到人」有几条（不改分类，只多一个读数）。"""
    if "users" not in _tables(con):
        return set()
    return {int(r[0]) for r in con.execute("select id from users")}


def read_audit_index(con: sqlite3.Connection) -> tuple[dict[str, dict[str, Any]], int]:
    """`action='qa.approved'` 的审计行按 `target` 建索引；**先按 action 过滤**（同一列还装着用户名/doc_id/模型名）。

    只有 `admin_id` 非空的行才进索引；`admin_id` 为 NULL 的行计入第二个返回值——设计卡 §10 第③条点名的
    「真库里有多少条 `qa.approved` 的 admin_id 是空的」就落在这个读数上。
    """
    if "audit_logs" not in _tables(con):
        return {}, 0
    by_target: dict[str, dict[str, Any]] = {}
    null_admin = 0
    cur = con.execute("select target, admin_id, created_at from audit_logs where action = ?", (QA_APPROVED_ACTION,))
    for r in cur.fetchall():
        if r["admin_id"] is None:
            null_admin += 1
            continue
        target = str(r["target"] if r["target"] is not None else "")
        prev = by_target.get(target)
        # 同一目标被批准多次 ⇒ 取**最早**那条（第一次人工核订才是 reviewed_at 的正解）
        if prev is None or str(r["created_at"] or "") < str(prev["created_at"] or ""):
            by_target[target] = {"admin_id": int(r["admin_id"]), "created_at": r["created_at"]}
    return by_target, null_admin


def classify_row(row: dict[str, Any], audit_by_target: dict[str, dict[str, Any]], threshold: float) -> str:
    """设计卡 §5 的三档分类。非 approved 的行不进这三档（计入 `not_approved`，既不隔离也不误标成人工核订）。"""
    if str(row.get("status") or "") != "approved":
        return NOT_APPROVED
    if audit_by_target.get(str(row["id"])) is not None:
        return HUMAN
    score = row.get("grounded_score")
    if score is not None and float(score) >= threshold:
        return AUTO_INFERRED
    return UNKNOWN


def read_vector_records_readonly(chroma_dir: Path | str, collection_name: str) -> list[dict[str, Any]]:
    """只读打开 `chroma.sqlite3` 取回该集合的记录（id / document / metadata），不经 chroma 客户端。

    为什么按 SQL 读：`chromadb.PersistentClient` 一打开就可能在同目录建 `-wal`/`-shm` 或跑自己的
    migration ⇒ 对真实目录那就不是只读。这里认的是 chroma 0.4.24 的 metadb 形状：
    `embeddings.embedding_id` 就是记录 id，`embedding_metadata` 里 `key='chroma:document'` 存正文。
    这条映射不是照文档猜的——
    `tests/test_backfill_qa_link.py::test_vector_reader_returns_the_very_doc_ids_the_product_wrote`
    拿产品自己写进去的 doc id 逐条对账，空库与正库两条腿都跑。
    """
    sqlite_path = Path(chroma_dir) / "chroma.sqlite3"
    if not sqlite_path.exists():
        return []
    con = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row  # 下面按 r["rid"] 取名；缺这行会在**非空**库上直接 TypeError（空库跑过所以没暴露）
    try:
        coll = con.execute("select id from collections where name = ?", (collection_name,)).fetchone()
        if coll is None:
            return []
        segs = [
            r[0] for r in con.execute("select id from segments where collection = ? and scope = 'METADATA'", (coll[0],))
        ]
        if not segs:
            return []
        records: dict[int, dict[str, Any]] = {}
        for seg in segs:
            cur = con.execute(
                "select e.id as rid, e.embedding_id as did, m.key as k,"
                " m.string_value as sv, m.int_value as iv, m.float_value as fv, m.bool_value as bv"
                " from embeddings e join embedding_metadata m on m.id = e.id"
                " where e.segment_id = ? order by e.id, m.key",
                (seg,),
            )
            for r in cur.fetchall():
                rec = records.setdefault(int(r["rid"]), {"id": r["did"], "document": "", "metadata": {}})
                key = str(r["k"])
                if key == "chroma:document":
                    rec["document"] = str(r["sv"] or "")
                    continue
                if r["sv"] is not None:
                    val: Any = r["sv"]
                elif r["iv"] is not None:
                    val = r["iv"]
                elif r["fv"] is not None:
                    val = r["fv"]
                elif r["bv"] is not None:
                    val = bool(r["bv"])
                else:
                    val = None
                rec["metadata"][key] = val
        return [records[k] for k in sorted(records)]
    finally:
        con.close()


# ==================== 计划（配对＋分类＋计数；纯函数，不写库） ====================
@dataclass
class Plan:
    counts: dict[str, int] = field(default_factory=dict)
    unknown_list: list[dict[str, Any]] = field(default_factory=list)
    row_updates: list[dict[str, Any]] = field(default_factory=list)
    new_rows: list[dict[str, Any]] = field(default_factory=list)
    superseded: list[dict[str, Any]] = field(default_factory=list)
    orphans: list[dict[str, Any]] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)


# 落盘白名单：登记行往外写的时候**只**带这些键。
# 为什么不写成「摘掉 question/answer」：黑名单会漏——`evidence` 里装着条文引用与法名（第一轮真库读数
# 就是这么漏出「消费者权益保护法|第二十五条」的），它既不是题干也不是答案，但同样属于语料内容，
# 票面 §2 第②条要的是「只有标识与计数」。白名单写错了会少写而不是多写，方向是安全的。
_EMIT_KEYS = (
    "register_kind",
    "id",
    "grounded_score",
    "status",
    "approval_source",
    "eligibility",
    "eligibility_version",
    "vector_doc_id",
    "_inserted_id",
)


def _strip_text(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """落盘形状按白名单投影：`new_rows` 里的正文/evidence 只在内存里用于 INSERT，一次都不许进产物。"""
    return [{k: v for k, v in r.items() if k in _EMIT_KEYS} for r in rows]


def _pair_key(question: Any, answer: Any) -> tuple[str, str]:
    """精确配对键：逐字相等。**不做**任何归一化（strip/小写/全半角/去空白全都算猜配，票面 A3 不许）。"""
    return (str(question), str(answer))


def _provable_rank(rec: dict[str, Any]) -> tuple[int, int]:
    """重复组里「可证来源」的排序：已带链 > 来源可校验（复用 `retrieval_core.qa_provenance_verifiable`）> 最早写入。

    值越小越优先。第三档用 SQLite 插入序兜底（记录已按 e.id 升序）⇒ 结果是**确定性**的而不是「随便挑一条」；
    这条决定哪条向量记录被保留，必须可复现。
    """
    seq = int(rec.get("_seq", 0))
    meta = rec.get("metadata") or {}
    if meta.get("qa_candidate_id") is not None:
        return (0, seq)
    import retrieval_core as rc

    if rc.qa_provenance_verifiable(meta):
        return (1, seq)
    return (2, seq)


def _owner_row(rows: list[dict[str, Any]], audit_by_target: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """同一 (q,a) 有多条 SQL 行时，向量指针给哪一条：有可证人工审批的先，其次 approved，其次 id 最小。"""
    if not rows:
        return None

    def rank(r: dict[str, Any]) -> tuple[int, int]:
        if audit_by_target.get(str(r["id"])) is not None:
            return (0, int(r["id"]))
        if str(r.get("status") or "") == "approved":
            return (1, int(r["id"]))
        return (2, int(r["id"]))

    return sorted(rows, key=rank)[0]


def build_plan(
    candidates: list[dict[str, Any]],
    vectors: list[dict[str, Any]],
    audit_by_target: dict[str, dict[str, Any]],
    threshold: float,
    null_admin_audit_rows: int = 0,
    known_admin_ids: set[int] | None = None,
) -> Plan:
    """把 SQL 行与向量记录按 `(question, answer)` 精确配对，产出分类计数与写入计划（纯函数，不写库）。"""
    known_admins = known_admin_ids or set()
    # 三档计数**总是**先置 0 再累加：某档真库里一条都没有时，读数表上必须出现 `... = 0` 这一行，
    # 而不是「键不存在」——「不存在」在表格里会被读成「没测」，而它测了、结果是 0。
    counts: dict[str, int] = {f"class:{label}": 0 for label in (HUMAN, AUTO_INFERRED, UNKNOWN)}
    plan = Plan()

    for i, v in enumerate(vectors):
        v["_seq"] = i
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for v in vectors:
        groups.setdefault(_pair_key(v.get("document", ""), (v.get("metadata") or {}).get("answer", "")), []).append(v)

    rows_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in candidates:
        rows_by_key.setdefault(_pair_key(row.get("question", ""), row.get("answer", "")), []).append(row)

    already_registered = {str(r["vector_doc_id"]) for r in candidates if r.get("vector_doc_id")}
    kept_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    owner_by_key: dict[tuple[str, str], dict[str, Any] | None] = {}
    now_iso = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # 1) 向量侧定档：每组保留一条，其余 superseded；组里没有 SQL 行的 ⇒ 孤儿
    for key in sorted(groups, key=lambda k: str(k)):
        grp = groups[key]
        ordered = sorted(grp, key=_provable_rank)
        kept = ordered[0]
        kept_by_key[key] = kept
        owner = _owner_row(rows_by_key.get(key, []), audit_by_target)
        owner_by_key[key] = owner

        for extra in ordered[1:]:
            counts["superseded_records"] = counts.get("superseded_records", 0) + 1
            plan.superseded.append(
                {
                    "doc_id": extra["id"],
                    "kept_doc_id": kept["id"],
                    "has_chain": (extra.get("metadata") or {}).get("qa_candidate_id") is not None,
                }
            )
            if extra["id"] in already_registered:
                continue  # 幂等：同一 doc id 已登记过 ⇒ 不再插行（连跑两次计数逐字相同）
            meta = extra.get("metadata") or {}
            plan.new_rows.append(
                {
                    "register_kind": "superseded",
                    "question": extra.get("document", ""),
                    "answer": meta.get("answer", ""),
                    "evidence": meta.get("evidence", "") or "",
                    "grounded_score": None,
                    "status": "approved",
                    "approval_source": UNKNOWN,
                    # 票面 §3 A4：重复的非保留条 ⇒ superseded（资格 revoked，不物理删）
                    "eligibility": "revoked",
                    "eligibility_version": 1,
                    "vector_doc_id": extra["id"],
                    "created_at": now_iso,
                }
            )

        kept_meta = kept.get("metadata") or {}
        if owner is None and kept["id"] not in already_registered:
            plan.orphans.append({"doc_id": kept["id"], "has_chain": kept_meta.get("qa_candidate_id") is not None})
            plan.new_rows.append(
                {
                    "register_kind": "orphan",
                    "question": kept.get("document", ""),
                    "answer": kept_meta.get("answer", ""),
                    "evidence": kept_meta.get("evidence", "") or "",
                    "grounded_score": None,
                    "status": "approved",
                    "approval_source": UNKNOWN,
                    # 修订三落点：无链记录的隔离面**显式标** unknown/quarantined，
                    # 不再靠「没写 vector_doc_id」这种隐式形状（隐式形状对读侧等于「状态轴不适用」）。
                    "eligibility": "quarantined",
                    "eligibility_version": 1,
                    "vector_doc_id": kept["id"],
                    "created_at": now_iso,
                }
            )

    # 2) SQL 侧逐条分类
    for row in candidates:
        cls = classify_row(row, audit_by_target, threshold)
        key = _pair_key(row.get("question", ""), row.get("answer", ""))
        kept = kept_by_key.get(key)
        owner = owner_by_key.get(key)
        matched = kept is not None and owner is not None and str(owner["id"]) == str(row["id"])
        has_vector = kept is not None
        counts[f"class:{cls}"] = counts.get(f"class:{cls}", 0) + 1

        before = {
            "status": row.get("status"),
            "approval_source": row.get("approval_source"),
            "reviewed_by": row.get("reviewed_by"),
            "reviewed_at": row.get("reviewed_at"),
            "eligibility": row.get("eligibility"),
            "vector_doc_id": row.get("vector_doc_id"),
        }
        after = dict(before)
        entry: dict[str, Any] = {
            "id": int(row["id"]),
            "classification": cls,
            "has_vector": has_vector,
            "matched_doc_id": kept["id"] if matched else None,
            "before": before,
        }
        if cls == HUMAN:
            audit = audit_by_target[str(row["id"])]
            after.update(
                {"approval_source": HUMAN, "reviewed_by": audit["admin_id"], "reviewed_at": audit["created_at"]}
            )
            if known_admins and audit["admin_id"] not in known_admins:
                counts["human_admin_id_unresolved"] = counts.get("human_admin_id_unresolved", 0) + 1
        elif cls == AUTO_INFERRED:
            after["approval_source"] = AUTO_INFERRED
        elif cls == UNKNOWN:
            after["approval_source"] = UNKNOWN
            after["eligibility"] = "quarantined"
            plan.unknown_list.append(
                {"id": int(row["id"]), "grounded_score": row.get("grounded_score"), "has_vector": has_vector}
            )
        if matched and kept is not None:
            after["vector_doc_id"] = kept["id"]
        entry["after"] = after
        if after != before:
            plan.row_updates.append(entry)
        else:
            counts["rows_already_in_shape"] = counts.get("rows_already_in_shape", 0) + 1

    counts["candidates_total"] = len(candidates)
    counts["approved_total"] = sum(1 for r in candidates if str(r.get("status") or "") == "approved")
    counts["vector_records"] = len(vectors)
    counts["vector_records_chained"] = sum(
        1 for v in vectors if (v.get("metadata") or {}).get("qa_candidate_id") is not None
    )
    counts["vector_records_unlinked"] = counts["vector_records"] - counts["vector_records_chained"]
    counts["duplicate_groups"] = sum(1 for grp in groups.values() if len(grp) > 1)
    counts.setdefault("superseded_records", 0)
    counts["orphan_records"] = len(plan.orphans)
    counts["orphan_records_without_chain"] = sum(1 for o in plan.orphans if not o["has_chain"])
    counts["matched_pairs"] = sum(1 for key in kept_by_key if owner_by_key.get(key) is not None)
    counts["unmatched_approved"] = sum(
        1
        for r in candidates
        if str(r.get("status") or "") == "approved"
        and kept_by_key.get(_pair_key(r.get("question", ""), r.get("answer", ""))) is None
    )
    counts["audit_rows_null_admin"] = null_admin_audit_rows
    counts["registered_rows_to_insert"] = len(plan.new_rows)
    plan.counts = counts
    plan.notes = {
        "threshold_source": "knowledge_service.AUTO_CURATE_THRESHOLD",
        "threshold": threshold,
        "pairing": "exact (question, answer) 逐字相等；无归一化、无模糊、无相似度匹配",
        "vector_dir": "只读：本脚本不写向量、不给向量记录写 metadata ⇒ 状态轴对存量无链记录不适用（隔离由修订三 gate③ 承担）",
        "output_contains_no_text": "unknown 名单、快照、计数 JSON 都不含题干/答案/内容哈希",
        "sql_rows_sharing_one_text_pair": sum(1 for v in rows_by_key.values() if len(v) > 1),
    }
    return plan


# ==================== 写入（只在副本上） ====================
def _qa_column_ddl() -> dict[str, str]:
    """资格六列的 DDL 从 `migrations._COLUMN_MIGRATIONS` 取——不落第二份，第二份早晚漂移。"""
    import migrations

    out: dict[str, str] = {}
    for table, col, ddl, default in migrations._COLUMN_MIGRATIONS:
        if table != "qa_candidates":
            continue
        out[col] = f"{col} {ddl}" + (f" DEFAULT {default}" if default is not None else "")
    missing = {
        "approval_source",
        "reviewed_by",
        "reviewed_at",
        "eligibility",
        "eligibility_version",
        "vector_doc_id",
    } - set(out)
    if missing:
        raise RuntimeError(f"migrations 里缺 qa_candidates 列定义：{sorted(missing)}（本脚本不许自带第二份 DDL）")
    return out


def ensure_columns(con: sqlite3.Connection) -> list[str]:
    """幂等补列（与 `migrations.run_migrations` 同一套 DDL）。返回本次真正加上的列名。"""
    have = table_columns(con, "qa_candidates")
    added: list[str] = []
    for col, ddl in _qa_column_ddl().items():
        if col in have:
            continue
        con.execute(f"ALTER TABLE qa_candidates ADD COLUMN {ddl}")
        added.append(col)
    con.commit()
    return added


def apply_plan(db_path: Path, plan: Plan, snapshot_path: Path | None) -> dict[str, Any]:
    """把计划写进**副本**库：UPDATE 已有行 ＋ INSERT 登记行，并落 before/after 快照（A5 的回退依据）。

    只写 SQL。向量目录对本函数没有任何句柄。
    """
    con = sqlite3.connect(db_path.as_posix(), timeout=30)
    stats: dict[str, Any] = {"added_columns": [], "updated_rows": 0, "inserted_rows": 0, "registered": {}}
    try:
        stats["added_columns"] = ensure_columns(con)
        cur_cols = table_columns(con, "qa_candidates")
        writable = [c for c in _WRITABLE_COLUMNS if c in cur_cols]
        for upd in plan.row_updates:
            after = upd["after"]
            sets = [c for c in writable if c in after]
            if not sets:
                continue
            con.execute(
                f"update qa_candidates set {', '.join(f'{c} = ?' for c in sets)} where id = ?",
                [after[c] for c in sets] + [upd["id"]],
            )
            stats["updated_rows"] += 1
        max_id = int(con.execute("select coalesce(max(id), 0) from qa_candidates").fetchone()[0])
        inserted_ids: list[int] = []
        for new in plan.new_rows:
            # **行身份形状（Owner 10-18 更正 20261018-044723de 的红线）**：
            # 不写 `id=max(id)+1`、不用 `INSERT OR IGNORE`——预分配 id 会与并发写入者（采纳端点/别的回填）
            # 撞号，而 SQLite 的 INTEGER PRIMARY KEY 一旦有人显式给值就照收 ⇒ 静默覆盖既有行。
            # 这里只交数据，id 由 SQLite 自己发（INTEGER PRIMARY KEY = rowid 别名，自增即唯一），
            # 幂等靠**内容键**（`vector_doc_id` 已登记过就不再插，见 build_plan 的 already_registered）。
            payload = {k: v for k, v in new.items() if k in cur_cols and k != "register_kind"}
            cols = sorted(payload)
            cur = con.execute(
                f"insert into qa_candidates ({', '.join(cols)}) values ({', '.join('?' for _ in cols)})",
                [payload[c] for c in cols],
            )
            row_id = int(cur.lastrowid or 0)
            inserted_ids.append(row_id)
            stats["inserted_rows"] += 1
            kind = str(new.get("register_kind"))
            stats["registered"][kind] = stats["registered"].get(kind, 0) + 1
            new["_inserted_id"] = row_id
        if inserted_ids and min(inserted_ids) <= max_id:
            raise RuntimeError(f"登记行拿到了重复/回退的 id：{inserted_ids[:5]}（既有行可能被覆盖）")
        con.commit()
        if snapshot_path is not None:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(
                json.dumps(_snapshot(plan, db_path, stats), ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    finally:
        con.close()
    return stats


def _snapshot(plan: Plan, db_path: Path, stats: dict[str, Any]) -> dict[str, Any]:
    """before/after 快照（A5）：**只含 id 与资格列值**，不含题干/答案/内容哈希。"""
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db": str(db_path),
        "counts": plan.counts,
        "before_after": [
            {"id": u["id"], "classification": u["classification"], "before": u["before"], "after": u["after"]}
            for u in plan.row_updates
        ],
        "registered": _strip_text(plan.new_rows),
        "restore": {
            "updated_row_ids": [u["id"] for u in plan.row_updates],
            "inserted_count": len(plan.new_rows),
            "note": "回退＝把 updated_row_ids 的 before 值写回；登记行不删（删数据不可撤销这条对行也成立）。",
        },
        "stats": stats,
    }


def restore_from_snapshot(db_path: Path, snapshot_path: Path) -> dict[str, Any]:
    """A5 的回退：把快照里的 before 值写回被改过的行（把 `eligibility` 改回 `ok` 走的就是这条路）。

    本脚本插入的登记行**不删**：它们带 `approval_source='unknown'`，不构成放行，且读数里单列可数。
    """
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(db_path.as_posix(), timeout=30)
    done = 0
    try:
        cur_cols = table_columns(con, "qa_candidates")
        writable = [c for c in _WRITABLE_COLUMNS if c in cur_cols]
        for item in snap.get("before_after", []):
            before = item["before"]
            sets = [c for c in writable if c in before]
            if not sets:
                continue
            con.execute(
                f"update qa_candidates set {', '.join(f'{c} = ?' for c in sets)} where id = ?",
                [before[c] for c in sets] + [item["id"]],
            )
            done += 1
        con.commit()
    finally:
        con.close()
    return {
        "restored_rows": done,
        "registered_rows_kept": len(snap.get("registered", [])),
        "snapshot": str(snapshot_path),
    }


# ==================== 读数③：直返候选集 ====================
def load_questions(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """题集文件：`{"questions":[{"id":..,"text":..}], ...其余键进 meta}`，或纯字符串列表。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        qs: list[Any] = raw
        meta: dict[str, Any] = {}
    else:
        qs = raw.get("questions") or []
        meta = {k: v for k, v in raw.items() if k != "questions"}
    items: list[dict[str, Any]] = []
    for i, q in enumerate(qs):
        if isinstance(q, str):
            items.append({"id": f"Q{i + 1:03d}", "text": q})
        else:
            items.append({"id": str(q.get("id") or f"Q{i + 1:03d}"), "text": str(q.get("text") or q.get("q") or "")})
    meta.setdefault("n", len(items))
    return items, meta


def hit_from_record(rec: dict[str, Any]) -> dict[str, Any]:
    """把一条向量记录整成 `search_qa` 的返回形状（**逐键照 `knowledge_service.search_qa`**）。

    读数③的记录级腿要的是「这条语料记录会不会被拿去答复」，所以按记录自己构造 hit。
    键拼错就会绕过某道门 ⇒ 键名与 product 那份一一对应，由
    `tests/test_backfill_qa_link.py::test_record_level_hit_shape_carries_every_gate_input` 钉住。
    """
    meta = rec.get("metadata") or {}
    return {
        "question": rec.get("document", ""),
        "answer": meta.get("answer", ""),
        "score": 1.0,
        "evidence": meta.get("evidence", ""),
        "law_as_of_basis": meta.get("law_as_of_basis", ""),
        "fingerprint": meta.get("options_fingerprint", ""),
        "qa_candidate_id": meta.get("qa_candidate_id"),
    }


def _offline_env(db_path: Path, chroma_dir: Path) -> None:
    """测量腿的环境：只指向副本＋本地嵌入＋零配额＋离线。绝不落真实路径（守卫已先拦过一遍）。"""
    os.environ["DATABASE_URL"] = "sqlite:///" + db_path.as_posix()
    os.environ["CHROMA_DIR"] = str(chroma_dir)
    os.environ["QUOTA_DB"] = str(chroma_dir.parent / "measure-quota.sqlite")
    os.environ.setdefault("EMBEDDING_PROVIDER", "local")
    os.environ.setdefault("RERANK_ENABLED", "false")
    os.environ.setdefault("EMBEDDING_QUOTA_TOTAL", "0")
    os.environ.setdefault("RERANK_QUOTA_TOTAL", "0")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("JWT_SECRET", "backfill-measure-only")
    os.environ.setdefault("LLM_API_KEY", "backfill-measure-only")
    os.environ.setdefault("LLM_BASE_URL", "https://offline.invalid/v1")
    os.environ.setdefault("FEATURE_SELF_REGISTER", "false")


def measure_direct_return(
    db_path: Path,
    chroma_dir: Path,
    questions: list[dict[str, Any]],
    set_meta: dict[str, Any] | None = None,
    *,
    per_record: bool = False,
    collection: str | None = None,
) -> dict[str, Any]:
    """逐题面跑**真码** `main._qa_direct_return`，报命中条数（票面 §2 第③条＋Owner 钉死的口径）。

    三条读数分开报，不合并成一句话：
     · `search_qa_hits`：`search_qa`（默认 0.7 门）回来几条；
     · `direct_return_hits`：再过全部出口门（0.92／状态轴／来源可校验／引用在库／分水岭／指纹）之后
       真的原样吐出去几条 —— **这条才是「直返候选集成员数」**；
     · `direct_return_hits_without_chain`：命中的语料记录里没有 `qa_candidate_id` 的条数。
       这条就是修订三 gate③ 一落地会掉出去的条数；gate③ 属生产面（另派），本脚本不代落地，
       也不靠写 metadata 自己造链（红线：对向量目录只读）。
    `per_record=True` 再跑一条记录级腿：对向量集合里每条记录按它自己的题面跑一次真码，
    数「会被服务」的记录数——这条才是「存量被隔离掉多少」的分母（题面级腿的分母只有题集大小）。

    副作用声明（不许含糊）：import `main` 会跑 `init_db()` ⇒ 给 `--db` **副本**补列；
    打开 chroma 会在副本目录里留下自己的文件。所以这条模式同样过真实路径守卫。
    """
    _offline_env(db_path, chroma_dir)

    import knowledge_service as ks
    import main

    per: list[dict[str, Any]] = []
    for q in questions:
        text = q["text"]
        hit = ks.search_qa(text)
        fired = main._qa_direct_return({"qa_hit": hit, "rewritten": text}) is not None if hit else False
        per.append(
            {
                "id": q["id"],
                "search_qa_hit": hit is not None,
                "score": (hit or {}).get("score"),
                "direct_return": fired,
                "chain": "linked" if (hit or {}).get("qa_candidate_id") is not None else "unlinked",
                "answer_len": len(str((hit or {}).get("answer") or "")) if fired else 0,
            }
        )
    out: dict[str, Any] = {
        "question_set": set_meta or {},
        "n_questions": len(per),
        "search_qa_hits": sum(1 for p in per if p["search_qa_hit"]),
        "direct_return_hits": sum(1 for p in per if p["direct_return"]),
        "direct_return_hits_linked": sum(1 for p in per if p["direct_return"] and p["chain"] == "linked"),
        "direct_return_hits_without_chain": sum(1 for p in per if p["direct_return"] and p["chain"] == "unlinked"),
        "qa_direct_return_threshold": main._QA_DIRECT_RETURN_THRESHOLD,
        "per_question": per,
    }
    if per_record:
        name = collection or resolve_collection_name()
        recs = [
            r
            for r in read_vector_records_readonly(chroma_dir, name)
            if (r.get("metadata") or {}).get("answer") is not None
        ]
        served = 0
        unlinked_served = 0
        for r in recs:
            hit = hit_from_record(r)
            if main._qa_direct_return({"qa_hit": hit, "rewritten": str(hit["question"])}) is None:
                continue
            served += 1
            if hit["qa_candidate_id"] is None:
                unlinked_served += 1
        out["record_level"] = {
            "collection": name,
            "records": len(recs),
            "served": served,
            "served_without_chain": unlinked_served,
            "quarantined": len(recs) - served,
        }
    return out


# ==================== CLI ====================
def resolve_threshold() -> float:
    """阈值只认 `knowledge_service.AUTO_CURATE_THRESHOLD` 这一份真源（本票不许自带第二份，更不许放宽）。"""
    from knowledge_service import AUTO_CURATE_THRESHOLD

    return float(AUTO_CURATE_THRESHOLD)


def resolve_collection_name() -> str:
    """集合名认 `rag_chain.QA_COLLECTION_NAME`（随 embedding provider 派生，同一个真源）。"""
    from rag_chain import QA_COLLECTION_NAME

    return str(QA_COLLECTION_NAME)


@contextmanager
def isolated_side_env() -> Iterator[None]:
    """dry-run 期间把产品模块的环境出口全拐到临时文件：哪怕某个 import 侧手滑连库，也连不到真实路径。

    本脚本自己的读数**只**走显式的 `connect_read_only(--db)` 与只读 `chroma.sqlite3`，不看这些变量。
    用完必须还原（同一个进程里还住着别的调用方——同 `chroma_dir_guard.isolated_chroma` 的纪律）：
    不还原就等于把测试进程里第一次惰性建 store 的落点偷偷改到临时目录，那是最难查的跨用例污染。
    """
    keys = ("DATABASE_URL", "QUOTA_DB", "CHROMA_DIR", "EMBEDDING_PROVIDER", "RERANK_ENABLED", "HF_HUB_OFFLINE")
    previous = {k: os.environ.get(k) for k in keys}
    tmp = Path(os.environ.get("TEMP", "/tmp")) / f"fazhi-backfill-dryrun-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = "sqlite:///" + (tmp / "untouched.db").as_posix()
    os.environ["QUOTA_DB"] = str(tmp / "untouched-quota.sqlite")
    os.environ["CHROMA_DIR"] = str(tmp / "untouched-chroma")
    os.environ.setdefault("EMBEDDING_PROVIDER", "local")
    os.environ.setdefault("RERANK_ENABLED", "false")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def read_plan(db_path: Path, chroma_path: Path, collection: str, threshold: float) -> Plan:
    """只读地跑出计划（dry-run 与 apply 共用同一台仪器，保证两边计数可比）。"""
    con = connect_read_only(db_path)
    try:
        candidates = read_candidates(con)
        audit, null_admin = read_audit_index(con)
        known_admins = read_known_admin_ids(con)
    finally:
        con.close()
    vectors = read_vector_records_readonly(chroma_path, collection)
    return build_plan(candidates, vectors, audit, threshold, null_admin, known_admins)


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def plan_json(plan: Plan) -> dict[str, Any]:
    """落盘形状：`new_rows` 的正文一律摘掉（INSERT 用完就不许再出现在任何产物里）。"""
    d = {
        "counts": plan.counts,
        "unknown_list": plan.unknown_list,
        "row_updates": plan.row_updates,
        "superseded": plan.superseded,
        "orphans": plan.orphans,
        "notes": plan.notes,
    }
    d["registered_rows"] = _strip_text(plan.new_rows)
    return d


def dispatch(args: argparse.Namespace) -> int:
    modes = [bool(args.apply), bool(args.restore), bool(args.measure_direct_return)]
    if sum(modes) > 1:
        raise RefusalError("[backfill_qa_link] 拒绝执行：--apply／--restore／--measure-direct-return 三者互斥。")

    if any(modes):
        db_p, chroma_p = require_explicit_targets(args.db, args.chroma, "write")
        assert_not_real_targets(args.db, args.chroma, "write")
        # 必须在**任何产品模块被 import 之前**把环境出口定好：`settings` 是首次 import 时读盘的，
        # 而 `resolve_threshold()` 就会把它引进来（knowledge_service → rag_chain → settings）。
        # 顺序放反的后果是现量抓到的：`main` 启动强校验读到空的 JWT_SECRET ⇒ 测量腿直接炸。
        _offline_env(db_p, chroma_p)
    else:
        db_p = Path(args.db).resolve() if args.db else DEFAULT_DB.resolve()
        chroma_p = Path(args.chroma).resolve() if args.chroma else DEFAULT_CHROMA.resolve()

    threshold = resolve_threshold()
    collection = args.collection or resolve_collection_name()
    json_out = Path(args.json_out).resolve() if args.json_out else None

    if args.dump_questions:
        vectors = read_vector_records_readonly(chroma_p, collection)
        items = sorted(
            [
                {"id": str(v["id"]), "text": v.get("document", "")}
                for v in vectors
                if (v.get("metadata") or {}).get("answer") is not None
            ],
            key=lambda d: str(d["id"]),
        )
        out_path = Path(args.dump_questions).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "collection": collection,
                    "ordering": "doc id 升序（可复现，但**不是**冻结集：题面来自语料本身）",
                    "questions": items,
                },
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"[dump-questions] {len(items)} 条 -> {out_path}")
        return 0

    if args.restore:
        if not args.snapshot:
            raise RefusalError("[backfill_qa_link:restore] 拒绝执行：--restore 必须配 --snapshot。")
        out = restore_from_snapshot(db_p, Path(args.snapshot).resolve())
        print("[restore] " + json.dumps(out, ensure_ascii=False))
        _write_json(json_out, {"mode": "restore", **out})
        return 0

    if args.measure_direct_return:
        if not args.questions:
            raise RefusalError("[backfill_qa_link:measure] 拒绝执行：必须给 --questions。")
        items_q, meta = load_questions(Path(args.questions).resolve())
        res = measure_direct_return(
            db_p, chroma_p, items_q, meta, per_record=bool(args.per_record), collection=collection
        )
        print(
            "[measure] "
            + json.dumps({k: v for k, v in res.items() if k != "per_question"}, ensure_ascii=False, indent=1)
        )
        _write_json(json_out, res)
        return 0

    plan = read_plan(db_p, chroma_p, collection, threshold)

    if args.apply:
        snap = Path(args.snapshot).resolve() if args.snapshot else db_p.parent / "W06-BACKFILL-SNAPSHOT.json"
        stats = apply_plan(db_p, plan, snap)
        print(f"[apply] {json.dumps(stats, ensure_ascii=False)}")
        print("[apply] 计数：" + json.dumps(plan.counts, ensure_ascii=False))
        print(f"[apply] 快照：{snap}")
        _write_json(json_out, {"mode": "apply", "stats": stats, "snapshot": str(snap), **plan_json(plan)})
        return 0

    print(f"[dry-run] 目标（只读）：db={db_p} chroma={chroma_p} collection={collection} threshold={threshold}")
    print("[dry-run] 计数：")
    for k in sorted(plan.counts):
        print(f"  {k} = {plan.counts[k]}")
    print(f"[dry-run] unknown 名单 {len(plan.unknown_list)} 条（只有 id/grounded_score/has_vector）：")
    for u in plan.unknown_list:
        print(f"  id={u['id']} grounded_score={u['grounded_score']} has_vector={u['has_vector']}")
    print("[dry-run] 未写任何字节：DB 以 mode=ro 打开，向量目录以只读 SQL 打开，且没有 chroma 客户端句柄。")
    _write_json(
        json_out,
        {
            "mode": "dry-run",
            "target": {"db": str(db_p), "chroma": str(chroma_p), "collection": collection},
            **plan_json(plan),
        },
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="存量 QA 候选链回填与分类读数（默认 dry-run）")
    ap.add_argument("--db", help="SQL 库路径（dry-run 默认＝backend/app.db **只读**；写模式必填且必须是副本）")
    ap.add_argument("--chroma", help="向量目录（dry-run 默认＝backend/chroma_db **只读**；写模式必填且必须是副本）")
    ap.add_argument("--apply", action="store_true", help="显式允许写（只准打副本）")
    ap.add_argument("--restore", action="store_true", help="按 --snapshot 的 before 值回退（只准打副本）")
    ap.add_argument("--measure-direct-return", action="store_true", help="逐题面跑真码数直返命中（只准打副本）")
    ap.add_argument("--snapshot", help="before/after 快照路径（apply 写、restore 读）")
    ap.add_argument("--questions", help="题集 JSON（配合 --measure-direct-return）")
    ap.add_argument(
        "--per-record", action="store_true", help="测量时再跑一条记录级腿（每条语料记录按自己的题面过真码）"
    )
    ap.add_argument("--dump-questions", help="把向量库题面按 doc id 升序写出（读数③记录级腿用，非冻结集）")
    ap.add_argument("--json-out", help="读数 JSON 落盘路径")
    ap.add_argument("--collection", help="集合名（默认取 rag_chain.QA_COLLECTION_NAME）")
    args = ap.parse_args(argv)
    write_mode = bool(args.apply or args.restore or args.measure_direct_return)
    try:
        if write_mode:
            return dispatch(args)
        # 只读模式：把产品模块的环境出口暂时拐走（用完还原，见 `isolated_side_env` 的说明）
        with isolated_side_env():
            return dispatch(args)
    except RefusalError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
