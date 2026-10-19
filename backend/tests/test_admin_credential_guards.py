"""本轮按"更优解"补的两道守卫，各配一正一负判据（2026-10-16）。

1. `real_kb` 写围栏：交给测试的是**生产语料索引本体**，原先"只读"只写在 docstring 里。
2. `seed_admin` 拒绝公知默认口令：它的报错文案一直承诺"禁止 admin12345 上线"，
   但代码只校了"空"，显式写 admin12345 照样种进库；判据与 `reset_admin_password` 共用
   `auth.PUBLIC_DEFAULT_PASSWORD`。

两条都写了"应该红"的对照：围栏真拦写入、seed 真拒公知值且不落库。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._fences import FENCED_CLONES, FENCED_WRITES, ReadOnlyStore

BACKEND = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 1) 写围栏


class _FakeCollection:
    def __init__(self):
        self.writes = 0
        self.reads = 0

    def count(self):
        self.reads += 1
        return 1234

    def get(self, **kwargs):
        self.reads += 1
        return {"ids": [], "metadatas": []}

    def add(self, *a, **k):
        self.writes += 1

    def upsert(self, *a, **k):
        self.writes += 1

    def delete(self, *a, **k):
        self.writes += 1


class _FakeStore:
    def __init__(self):
        self._collection = _FakeCollection()
        self.docs_written = 0

    def add_documents(self, docs, **kwargs):
        self.docs_written += 1
        return ["x"]

    def similarity_search_with_score(self, q, k=4, filter=None):
        return []


def test_read_fence_passes_reads_through():
    from tests._fences import ReadOnlyStore

    store = _FakeStore()
    fenced = ReadOnlyStore(store)

    assert fenced._collection.count() == 1234, "读必须原样放行，否则真实语料用例会集体假跳过"
    assert fenced.similarity_search_with_score("q") == []
    assert store._collection.reads == 1


@pytest.mark.parametrize("name", sorted(FENCED_WRITES | FENCED_CLONES))
def test_every_fenced_name_raises_on_both_layers(name):
    """围栏里**每一个**名字，从外壳和从 `_collection` 两层打进来都必须当场抛。

    按名单驱动而不是按 5 个手写 lambda 驱动：名单以后会因为"真类上新增写方法"而变长，
    手写 lambda 就会悄悄落后于名单（本次实测第一轮就是这么漏了 6 个名字）。
    这里 getattr 本身就该抛，所以替身类有没有这个方法都无关——判据钉的是围栏，不是替身。
    """
    store = _FakeStore()
    fenced = ReadOnlyStore(store)

    with pytest.raises(AssertionError, match="禁止"):
        getattr(fenced, name)
    with pytest.raises(AssertionError, match="禁止"):
        getattr(fenced._collection, name)

    assert store.docs_written == 0, "写穿透到了真对象，围栏是假的"
    assert store._collection.writes == 0, "写穿透到了 collection，围栏是假的"


def test_inner_reference_is_not_readable_on_either_layer():
    """`fenced._inner` 曾经是个可读 slot ⇒ 拿到裸对象就能写，围栏形同虚设。"""
    store = _FakeStore()
    fenced = ReadOnlyStore(store)

    escaped = None
    with pytest.raises(AssertionError, match="内层引用"):
        escaped = fenced._inner
    assert escaped is None

    with pytest.raises(AssertionError, match="内层引用"):
        escaped = fenced._collection._inner
    assert escaped is None

    assert store.docs_written == 0 and store._collection.writes == 0


def test_repr_does_not_touch_the_real_store():
    """pytest 失败时会 repr 现场对象；repr 若去碰真库，调试输出自己就成了副作用。"""
    store = _FakeStore()
    fenced = ReadOnlyStore(store)
    before = (store.docs_written, store._collection.reads, store._collection.writes)

    assert "ReadOnlyStore" in repr(fenced)
    assert "ReadOnlyCollection" in repr(fenced._collection)
    assert (store.docs_written, store._collection.reads, store._collection.writes) == before


_WRITE_VERBS = ("add", "delete", "upsert", "update", "modify", "reset", "insert", "create")


def _real_write_surface() -> set[str]:
    """已安装的真类上"写语义"的方法名，剔除 pydantic/object 自带的模型管线名。

    剔除那一步是必须的：`update_forward_refs`/`model_copy`/`construct` 这些含写动词却属于
    BaseModel 管线，把它们当写入围栏会让代理对象在 pydantic 内部路径上自毁。
    """
    import chromadb
    from langchain_chroma import Chroma
    from pydantic import BaseModel

    plumbing = set(dir(BaseModel)) | set(dir(object))
    out: set[str] = set()
    for cls in (Chroma, chromadb.Collection):
        for n in dir(cls):
            if n.startswith("__") or n in plumbing:
                continue
            if any(v in n.lower() for v in _WRITE_VERBS):
                out.add(n)
    return out


def test_fence_covers_real_write_surface():
    """名单必须覆盖已安装类的全集：升级 langchain/chromadb 新增写入口时这条会红，而不是静默漏。"""
    surface = _real_write_surface()
    missing = sorted(surface - FENCED_WRITES)
    assert not missing, f"真类上有写方法没进围栏：{missing}（Chroma/Collection 的写面变宽了，围栏要跟着补）"


def test_fence_does_not_block_read_names():
    """反向：读名字绝不许进名单，否则 real_kb 用例会集体"看着过、其实什么都没查"。"""
    blocked_reads = sorted(FENCED_WRITES & {"count", "get", "query", "peek", "similarity_search"})
    assert not blocked_reads, f"围栏挡住了读方法：{blocked_reads}"


# ---------------------------------------------------------------- 2) seed 守卫


def _run_seed(tmp_path, monkeypatch_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(monkeypatch_env)
    env["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'seed.db').as_posix()}"
    env["QUOTA_DB"] = str(tmp_path / "quota.sqlite")
    env["CHROMA_DIR"] = str(tmp_path / "chroma")
    env["JWT_SECRET"] = "test-jwt-secret-for-ci-only"
    env["LLM_API_KEY"] = "test-key-not-for-real-calls"
    env["LLM_BASE_URL"] = "https://test.invalid/v1"
    env["EMBEDDING_PROVIDER"] = "local"
    env["PYTHONPATH"] = str(BACKEND)
    return subprocess.run(
        [sys.executable, str(BACKEND / "seed_admin.py")],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
        env=env,
        timeout=300,
    )


def test_seed_refuses_public_default_password(tmp_path):
    """显式写 admin12345 必须被拒（这是它报错文案早就承诺过的行为）。"""
    proc = _run_seed(tmp_path, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "admin12345"})

    assert proc.returncode == 1, f"应拒绝公知默认口令，实际 rc={proc.returncode}：{proc.stdout[-300:]}"
    assert "公知默认" in (proc.stdout + proc.stderr), (proc.stdout + proc.stderr)[-400:]
    # 校验排在 init_db() 之前 ⇒ 一次拒绝必须什么都不产生（原先先建表再拒，留下一个空库文件）。
    assert not (tmp_path / "seed.db").exists(), "拒了却还是把库建出来了"
    assert _admin_rows(tmp_path) == 0, "拒了却还是把管理员种进了库"


def test_seed_refuses_placeholder_change_me_end_to_end(tmp_path):
    """端到端：`ADMIN_PASSWORD=change_me`（仓库根 .env.example 原值）必须被拒并给非零退出、且不落库。"""
    proc = _run_seed(tmp_path, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "change_me"})

    assert proc.returncode == 1, f"应拒绝 change_me，实际 rc={proc.returncode}：{(proc.stdout + proc.stderr)[-300:]}"
    assert not (tmp_path / "seed.db").exists(), "拒了却还是把库建出来了"
    assert _admin_rows(tmp_path) == 0, "拒了却还是把管理员种进了库"


def test_public_default_constant_is_the_known_leaked_value():
    """守卫挡的必须**就是**仓库历史里泄漏过的那个值：常量一旦被改掉，两条拒绝会静默失去对象。

    这条不是同义反复——它比的不是自己，是 `auth` 里的单一真源与"外部已知的那个口令值"，
    而 `test_reset_admin_password.py` 现在也从同一个常量取值（不再有第二份手抄）。
    """
    from auth import PUBLIC_DEFAULT_PASSWORD, is_public_default_password

    assert PUBLIC_DEFAULT_PASSWORD == "admin12345", "公知默认口令的值变了 ⇒ 守卫不再挡住真实泄漏值"
    assert is_public_default_password("admin12345") is True
    assert is_public_default_password("a-nother-password") is False, "判据恒真＝两条拒绝用例都是假的"


# C05 = 「拒绝显式公知口令」（W09-E）：判据从小集合（单一真源）取，不再只等于一个历史泄漏值。
# 大小写/首尾空白变体也一并拒绝——归一化是有意的收紧。
_PLACEHOLDER_VARIANTS = ("change_me", " Change_Me ", "CHANGEME", "your_password", "password", "123456")


@pytest.mark.parametrize("value", _PLACEHOLDER_VARIANTS)
def test_placeholder_passwords_are_refused_by_the_guard(value):
    """模板占位/历史泄漏/最常见弱口令都必须在拒斥集内。

    否则 `cp .env.example .env && docker compose up` 就照样种出弱口令 admin。
    """
    from auth import is_public_default_password

    assert is_public_default_password(value) is True, f"{value!r} 应被判为公知口令"


def test_guard_still_accepts_a_long_unique_passphrase():
    """反向控制：拒斥集是**刻意小集合**、不是通用口令强度策略，合法长口令不得被误伤。"""
    from auth import is_public_default_password

    assert is_public_default_password("a-long-unique-passphrase") is False


def test_public_default_has_exactly_one_definition_site():
    """公知口令的值只许出现在 `auth.py` 一处；别处再写一遍字面量就是重新分叉。

    用"文件里还有没有这个字面量"来钉，而不是 `A is B`——短 ASCII 字面量会被 Python 驻留，
    两份手抄的 `is` 也可能为真，那种判据根本量不到分叉。
    """
    sites = {
        "auth.py": True,  # 唯一定义处
        "seed_admin.py": False,
        "scripts/reset_admin_password.py": False,
        "tests/test_reset_admin_password.py": False,
    }
    offenders = []
    for rel, may_define in sites.items():
        text = (BACKEND / rel).read_text(encoding="utf-8")
        has_literal = '"admin12345"' in text or "'admin12345'" in text
        if has_literal != may_define:
            offenders.append(rel)
    assert not offenders, f"公知默认口令又出现了第二份手抄：{offenders}（判据应统一取 auth.PUBLIC_DEFAULT_PASSWORD）"


def test_root_env_example_has_no_copy_and_run_admin_password():
    """静态门：候选工作树根 `.env.example` 的 `ADMIN_PASSWORD` 必须是空值。

    原先写 `ADMIN_PASSWORD=change_me` ⇒ `cp .env.example .env && docker compose up` 直接种出
    admin/change_me（公知口令上线）。修复后模板不再提供任何可 copy-and-run 的占位口令。
    """
    env_example = BACKEND.parent / ".env.example"
    values = [
        line.split("=", 1)[1].strip()
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("ADMIN_PASSWORD=")
    ]
    assert values, f"{env_example} 里找不到 ADMIN_PASSWORD 行"
    assert all(v == "" for v in values), f"ADMIN_PASSWORD 仍留可 copy-and-run 的占位口令：{values!r}"


def test_seed_still_refuses_empty_password(tmp_path):
    """既有拒绝不得被本次改动破坏（执行书 W09：不能为造红去动已有守卫）。"""
    proc = _run_seed(tmp_path, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": ""})

    assert proc.returncode == 1
    assert "未设置 ADMIN_PASSWORD" in (proc.stdout + proc.stderr)


def test_seed_accepts_a_non_public_password(tmp_path):
    """正向控制：换成非公知口令就必须正常创建，否则上面两条是"恒拒"的假判据。"""
    proc = _run_seed(tmp_path, {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "a-long-unique-passphrase"})

    assert proc.returncode == 0, f"合法口令应能播种：rc={proc.returncode} {(proc.stdout + proc.stderr)[-400:]}"
    assert _admin_rows(tmp_path) == 1


def _admin_rows(tmp_path) -> int:
    import sqlite3

    db = tmp_path / "seed.db"
    if not db.exists():
        return 0
    con = sqlite3.connect(str(db))
    try:
        return int(con.execute("select count(*) from users where role='admin'").fetchone()[0])
    except Exception:
        return 0
    finally:
        con.close()
