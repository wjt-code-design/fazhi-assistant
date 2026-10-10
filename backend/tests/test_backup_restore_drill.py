"""E.3 备份→恢复演练（合成数据，全程不接触真实库）。

与 `test_backup_data.py` 的分工：那只文件钉的是**失败关闭契约**（15 条：目标复用拒绝、
源缺失、验证抛异常、附属件映射、清单构建失败……）。本文件钉的是**可用面**——
"这个包能不能真的把数据恢复出来并查得动"，因为只会红的测试不证明备份能用：

- 行内容比对（不是只数行数）：恢复库里取回合成条文原文。
- 引用比对：恢复向量库按查询向量命回合成条文的 `source`×`article`，并与包内 `chroma_index.json` 对齐。
- WAL 形状：源库开 WAL，备份必须是单文件且不带 `-wal`/`-shm` 残留。
- 不覆盖原输入：备份前后、恢复之后，源对象逐只 sha 不变。
- 路径分歧：`_check_env_contract()` 必须在**动手之前**拒绝（`CHROMA_DIR`/`QUOTA_DB` 与固定目标不一致）。

向量一律显式传入：chromadb 的默认 embedding function 会去下载 mini-lm —— 那既违反本轮
"不出网"护栏，也让测试依赖网络。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import chromadb
import pytest

import rag_chain
from scripts import backup_data

SENTINEL_LAW = "中华人民共和国合同法"
SENTINEL_ARTICLE = "第一百九十七条"
SENTINEL_TEXT = "合同的订立，应当遵循诚实信用原则。本节为合成演练文本，非真实条文。"
QUOTA_SENTINEL = "probe-model-a"

# 两条彼此可分的合成条文：查询向量与第一条同向，命中必须是它。
DOCS = [
    {"id": "doc-1", "text": SENTINEL_TEXT, "source": f"{SENTINEL_LAW}{SENTINEL_ARTICLE}", "article": SENTINEL_ARTICLE},
    {
        "id": "doc-2",
        "text": "借款人应当按照约定的期限支付利息。合成演练文本。",
        "source": "中华人民共和国民法典第六百七十四条",
        "article": "第六百七十四条",
    },
]
VEC_1 = [1.0] + [0.0] * 7
VEC_2 = [0.0, 1.0] + [0.0] * 6
QUERY_VEC = [0.9, 0.1] + [0.0] * 6


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    """root 下每个文件的 sha256（相对路径为键）——用于"原输入没被动过"。"""
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def make_main_db(path: Path, wal: bool = True) -> None:
    con = sqlite3.connect(path)
    with con:
        if wal:
            con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE laws (law_name TEXT, article TEXT, body TEXT)")
        con.execute("INSERT INTO laws VALUES (?,?,?)", (SENTINEL_LAW, SENTINEL_ARTICLE, SENTINEL_TEXT))
        con.execute("INSERT INTO laws VALUES (?,?,?)", ("中华人民共和国民法典", "第六百七十四条", "合成第二条"))
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    if wal:
        # 前置自检（memory：尺子要先能红）：演练声称"源库是 WAL 形状"，就得当场量一次。
        assert mode == "wal", f"演练要求源库开 WAL，实际 {mode}"
    else:
        assert mode != "wal", f"这条腿要的是非 WAL 形状，实际 {mode}"


def make_quota_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE quota (model TEXT PRIMARY KEY, used INTEGER, total INTEGER)")
        con.execute("INSERT INTO quota VALUES (?,?,?)", (QUOTA_SENTINEL, 17, 100))
    con.close()


def make_chroma(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(root))
    col = client.get_or_create_collection(rag_chain.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    col.add(
        ids=[d["id"] for d in DOCS],
        documents=[d["text"] for d in DOCS],
        metadatas=[{"source": d["source"], "article": d["article"]} for d in DOCS],
        embeddings=[VEC_1, VEC_2],
    )
    assert col.count() == 2


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """一棵合成数据树 + 把 backup_data 的全部固定目标搬进去。

    `backup_data` 的隔离**不是**靠 `DATABASE_URL` 一项：CHROMA_DIR / DATA_DIR / MEDIA_DIR /
    QUOTA_SOURCE / DEFAULT_BACKUP_ROOT 全是模块级常量 ⇒ 逐个 patch，漏一个就写到真实目录上。
    """
    host = tmp_path / "host"
    (host / "data").mkdir(parents=True)
    main_db = host / "app.db"
    make_main_db(main_db)
    make_quota_db(host / "data" / "quota_used.sqlite")
    make_main_db(host / "data" / "app.db", wal=False)  # compose 挂进容器的那份库，形状不同
    chroma = host / "chroma_db"
    make_chroma(chroma)
    media = host / "media"
    media.mkdir()
    (media / "upload-1.txt").write_text("合成上传件", encoding="utf-8")

    for name, value in (
        ("DB_PATH", str(main_db)),
        ("CHROMA_DIR", str(chroma)),
        ("DATA_DIR", str(host / "data")),
        ("MEDIA_DIR", str(media)),
        ("QUOTA_SOURCE", str(host / "data" / "quota_used.sqlite")),
        ("DEFAULT_BACKUP_ROOT", str(tmp_path / "backups")),
    ):
        monkeypatch.setattr(backup_data, name, value)
    monkeypatch.delenv("CHROMA_DIR", raising=False)
    monkeypatch.delenv("QUOTA_DB", raising=False)
    return {"host": host, "tmp": tmp_path, "main_db": main_db, "chroma": chroma, "media": media, "data": host / "data"}


def run_backup(world, out=None, argv_extra=()):
    out = Path(out or world["tmp"] / "pkg")
    rc = backup_data.main(["--out", str(out), *argv_extra])
    return rc, out


def restore(world, pkg: Path, dest_root: Path) -> dict:
    """按包内清单把 dest 放回 dest_root（**不是**放回原 source —— 演练要能证"不覆盖原输入"）。"""
    manifest = json.loads((pkg / backup_data.MANIFEST_NAME).read_text(encoding="utf-8"))
    dest_root.mkdir(parents=True, exist_ok=True)
    placed = {}
    for entry in manifest["entries"]:
        src = pkg / entry["dest"]
        dst = dest_root / entry["dest"]
        if entry["kind"] == "dir":
            shutil.copytree(src, dst)
        else:
            shutil.copyfile(src, dst)
        placed[entry["dest"]] = (dst, entry)
    return placed


def test_drill_backup_succeeds_and_manifest_covers_every_surface(world):
    rc, pkg = run_backup(world)
    assert rc == 0
    manifest = json.loads((pkg / backup_data.MANIFEST_NAME).read_text(encoding="utf-8"))
    dests = {e["dest"] for e in manifest["entries"]}
    assert dests == {"app.db", "chroma_db", "chroma_index.json", "data_app.db", "media", "quota_used.sqlite"}
    # WAL 形状：备份必须是单文件，包里不许留 -wal/-shm 或验证残留
    assert not list(pkg.rglob("*.wal")) and not list(pkg.rglob("*.shm"))
    assert not list(pkg.rglob("*.verify.tmp"))
    sqlite_entries = [e for e in manifest["entries"] if e["kind"] == "sqlite"]
    assert sqlite_entries and all(e["integrity_check"] == "ok" for e in sqlite_entries)


def test_drill_restored_main_db_returns_the_sentinel_row_not_just_a_count(world):
    _, pkg = run_backup(world)
    placed = restore(world, pkg, world["tmp"] / "restored")
    db, entry = placed["app.db"]
    assert entry["source"] == str(world["main_db"]), "清单没记回真实 source 位置，恢复时无从下手"
    con = sqlite3.connect(db)
    row = con.execute("SELECT law_name, article, body FROM laws WHERE article=?", (SENTINEL_ARTICLE,)).fetchone()
    con.close()
    assert row == (SENTINEL_LAW, SENTINEL_ARTICLE, SENTINEL_TEXT), "恢复库取不回合成条文原文"


def test_drill_restored_quota_ledger_keeps_its_own_numbers(world):
    _, pkg = run_backup(world)
    placed = restore(world, pkg, world["tmp"] / "restored")
    con = sqlite3.connect(placed["quota_used.sqlite"][0])
    row = con.execute("SELECT model, used, total FROM quota").fetchone()
    con.close()
    assert row == (QUOTA_SENTINEL, 17, 100)


def test_drill_restored_vector_store_answers_the_query_with_the_right_citation(world):
    _, pkg = run_backup(world)
    placed = restore(world, pkg, world["tmp"] / "restored")
    col = chromadb.PersistentClient(path=str(placed["chroma_db"][0])).get_collection(rag_chain.COLLECTION_NAME)
    hit = col.query(query_embeddings=[QUERY_VEC], n_results=1)
    assert hit["ids"][0] == ["doc-1"]
    assert hit["metadatas"][0][0]["article"] == SENTINEL_ARTICLE
    assert hit["documents"][0][0] == SENTINEL_TEXT

    idx = json.loads((pkg / "chroma_index.json").read_text(encoding="utf-8"))
    assert idx["count"] == 2
    assert {(r["source"], r["article"]) for r in idx["items"]} == {(d["source"], d["article"]) for d in DOCS}, (
        "包内可读索引与恢复库的引用对不上"
    )


def test_drill_is_repeatable_and_never_touches_the_original_inputs(world):
    _, pkg = run_backup(world)
    inputs_before = snapshot(world["host"])
    restore(world, pkg, world["tmp"] / "restored")
    restore(world, pkg, world["tmp"] / "restored2")
    first_manifest = sha(pkg / backup_data.MANIFEST_NAME)
    rc2, _ = run_backup(world, out=pkg)
    assert rc2 == 2, "同一个包目录第二次必须拒绝覆盖"
    assert sha(pkg / backup_data.MANIFEST_NAME) == first_manifest
    assert snapshot(world["host"]) == inputs_before, "备份/恢复动了原输入字节"


def test_drill_writes_no_manifest_when_a_mid_way_step_fails(world, monkeypatch):
    real_copytree = shutil.copytree

    def boom(src, dst, *a, **kw):
        if str(dst).endswith("media"):
            raise OSError("media 复制半途失败")
        return real_copytree(src, dst, *a, **kw)

    # 打在 shutil 模块上并原样放行其它调用：backup_data.shutil 就是它，verify_sqlite 还要用 copyfile
    monkeypatch.setattr(shutil, "copytree", boom)
    rc, pkg = run_backup(world)
    assert rc == 1
    assert not (pkg / backup_data.MANIFEST_NAME).exists(), "坏包里不许带一份看起来完整的清单凭证"


def test_env_contract_guard_refuses_divergent_targets_before_any_work(world, monkeypatch):
    """守卫必须在读写之前拒：错目标备份 = 把错的库当成备份。"""
    monkeypatch.setenv("CHROMA_DIR", str(world["tmp"] / "elsewhere-chroma"))
    with pytest.raises(SystemExit) as exc:
        backup_data._check_env_contract()
    assert "backup_data" in str(exc.value)

    monkeypatch.delenv("CHROMA_DIR")
    monkeypatch.setenv("QUOTA_DB", str(world["tmp"] / "elsewhere-quota.sqlite"))
    with pytest.raises(SystemExit):
        backup_data._check_env_contract()

    # unset 才放行；这里把 env 指回固定目标，证守卫在"一致"时不误拒（否则它只是恒红）。
    monkeypatch.setenv("QUOTA_DB", backup_data.QUOTA_SOURCE)
    monkeypatch.setenv("CHROMA_DIR", str(world["chroma"]))
    backup_data._check_env_contract()
