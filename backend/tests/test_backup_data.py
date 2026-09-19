"""Fail-closed contracts for the production backup helper.

桩一律走 `monkeypatch.setattr(module, "NAME", value)` 的**默认严格模式**（不关属性存在性检查）：
桩打在**存在**的属性上才有意义 —— 一旦生产码改名，严格模式立刻报错，而静默失效的桩会让测试
转而读写**真实** `backend/data/`（隔离隐患，评审 §3#6）。
`EXTRA_SQLITE` 的源由 `DATA_DIR` + 包内名映射算出 ⇒ 测试只 patch `DATA_DIR`，映射本身留在被测面。
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from scripts import backup_data


def test_backup_refuses_to_reuse_existing_target_directory(tmp_path, monkeypatch, capsys):
    target = tmp_path / "backup"
    target.mkdir()
    marker = target / "existing.txt"
    marker.write_text("immutable evidence\n", encoding="utf-8")
    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "missing.db"))

    exit_code = backup_data.main(["--out", str(target), "--skip-chroma"])

    assert exit_code == 2
    assert marker.read_text(encoding="utf-8") == "immutable evidence\n"
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_sqlite_source_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_sqlite_restore_verification_fails(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))
    monkeypatch.setattr(backup_data, "backup_sqlite", lambda *_: str(tmp_path / "backup" / "app.db"))
    monkeypatch.setattr(backup_data, "verify_sqlite", lambda *_: (False, "corrupt"))

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_sqlite_backup_raises(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))

    def fail_backup(*_):
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(backup_data, "backup_sqlite", fail_backup)

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_sqlite_verification_raises(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))
    monkeypatch.setattr(backup_data, "backup_sqlite", lambda *_: str(tmp_path / "backup" / "app.db"))

    def fail_verify(*_):
        raise sqlite3.DatabaseError("cannot verify")

    monkeypatch.setattr(backup_data, "verify_sqlite", fail_verify)

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_requires_chroma_unless_explicitly_skipped(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "missing-chroma"))
    monkeypatch.setattr(backup_data, "backup_sqlite", lambda *_: str(tmp_path / "backup" / "app.db"))
    monkeypatch.setattr(backup_data, "verify_sqlite", lambda *_: (True, "ok"))

    exit_code = backup_data.main(["--out", str(tmp_path / "backup")])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_chroma_export_fails(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    chroma = tmp_path / "chroma_db"
    chroma.mkdir()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(chroma))
    monkeypatch.setattr(backup_data, "backup_sqlite", lambda *_: str(tmp_path / "backup" / "app.db"))
    monkeypatch.setattr(backup_data, "verify_sqlite", lambda *_: (True, "ok"))
    monkeypatch.setattr(backup_data.shutil, "copytree", lambda *_: Path(tmp_path / "backup" / "chroma_db"))

    def fail_export(_: str) -> str:
        raise RuntimeError("export failed")

    monkeypatch.setattr(backup_data, "export_chroma_json", fail_export)

    exit_code = backup_data.main(["--out", str(tmp_path / "backup")])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def test_backup_returns_nonzero_when_chroma_copy_fails(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.db"
    source.touch()
    chroma = tmp_path / "chroma_db"
    chroma.mkdir()
    monkeypatch.setattr(backup_data, "DB_PATH", str(source))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(chroma))
    monkeypatch.setattr(backup_data, "backup_sqlite", lambda *_: str(tmp_path / "backup" / "app.db"))
    monkeypatch.setattr(backup_data, "verify_sqlite", lambda *_: (True, "ok"))

    def fail_copy(*_):
        raise OSError("copy failed")

    monkeypatch.setattr(backup_data.shutil, "copytree", fail_copy)

    exit_code = backup_data.main(["--out", str(tmp_path / "backup")])

    assert exit_code == 1
    assert "备份完成" not in capsys.readouterr().out


def _seed_sqlite(path, marker):
    """建一个真能打开的最小 SQLite 库，并写入**可区分**的哨兵值。

    marker 三份必须各不相同（S4 版两份源库都插 `'x'`）：只有内容可区分，断言才钉得住
    "包里的 quota 来自 quota 那一份源"，而不是"包里多出一个文件"。
    """
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        con.execute("INSERT INTO t (v) VALUES (?)", (marker,))
    con.close()


def _read_marker(path):
    """读出哨兵值（只读打开，不创建）—— 断言"包内这个库到底是谁"。"""
    con = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("SELECT v FROM t").fetchone()[0]
    finally:
        con.close()


def test_backup_maps_each_extra_source_to_its_own_package_name(tmp_path, monkeypatch, capsys):
    """S4 缺口 + S7 精度：三件附属都进包，且**包内每个库的内容来自它自己那份源**。

    摆位刻意与真仓库同构（主库 `tmp_path/app.db`、两份附属在 `tmp_path/data/` 下）：
    M6 变异把 `data_app.db` 的源改成 `../app.db`（从 DATA_DIR 往上一级），落点正是主库 ⇒
    备份出一个**能打开、内容却是主库**的 `data_app.db`，这条才因"内容不对"而红。
    若主库起名 `main.db`，M6 会因源不存在被 skipped ⇒ 红错原因，那道变异什么都没证明。
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_sqlite(tmp_path / "app.db", "main")
    _seed_sqlite(data_dir / "quota_used.sqlite", "quota")
    _seed_sqlite(data_dir / "app.db", "dataapp")
    media = tmp_path / "media"
    (media / "sub").mkdir(parents=True)
    (media / "sub" / "a.png").write_bytes(b"\x89PNG-7")

    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(backup_data, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(media))

    out = tmp_path / "backup"
    exit_code = backup_data.main(["--out", str(out), "--skip-chroma"])

    assert exit_code == 0, capsys.readouterr().out
    assert _read_marker(out / "app.db") == "main"
    assert _read_marker(out / "quota_used.sqlite") == "quota", "包内 quota 装的不是 quota 源库 ⇒ 源↔目标映射错了"
    assert _read_marker(out / "data_app.db") == "dataapp", "包内 data_app.db 装的不是容器侧库 ⇒ 源↔目标映射错了"
    assert (out / "media" / "sub" / "a.png").read_bytes() == b"\x89PNG-7"

    manifest = json.loads((out / backup_data.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert [e["dest"] for e in manifest["entries"]] == ["app.db", "data_app.db", "media", "quota_used.sqlite"]
    by_dest = {e["dest"]: e for e in manifest["entries"]}
    assert by_dest["quota_used.sqlite"]["integrity_check"] == "ok"
    assert by_dest["quota_used.sqlite"]["source"] == str(data_dir / "quota_used.sqlite")
    # media 此前**零验证**（文件不变式"光备份不验证等于没备份"对它从未适用）：清单逐个哈希补上
    assert by_dest["media"]["items"] == [
        {"path": "sub/a.png", "bytes": 6, "sha256": hashlib.sha256(b"\x89PNG-7").hexdigest()}
    ]


def test_backup_tolerates_absent_extras_and_says_so(tmp_path, monkeypatch, capsys):
    """缺件不该让整个备份失败（干净机器上可能就没有 media/容器库），但必须**说出原因+名字**。"""
    _seed_sqlite(tmp_path / "app.db", "main")
    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(backup_data, "DATA_DIR", str(tmp_path / "empty_data"))
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(tmp_path / "no_media"))

    out = tmp_path / "backup"
    exit_code = backup_data.main(["--out", str(out), "--skip-chroma"])
    printed = capsys.readouterr().out

    assert exit_code == 0, printed
    assert not (out / "quota_used.sqlite").exists()
    # 断言必须指向**具体缺的是哪件、为什么缺**——旧版只断言名字在输出里，连"原因说没说出来"
    # 都没钉住；而只断言"跳过"更会被 `--skip-chroma 跳过` 那条骗过（本票第一轮就中招）。
    assert "跳过（源不存在）：quota_used.sqlite" in printed, printed
    assert "跳过（源不存在）：media" in printed, printed
    # 缺件不进清单：清单回答的是"包里到底有什么"
    manifest = json.loads((out / backup_data.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert [e["dest"] for e in manifest["entries"]] == ["app.db"]


def test_backup_fails_closed_when_extra_sqlite_is_corrupt(tmp_path, monkeypatch, capsys):
    """附属库校验不过 ⇒ 整个备份判失败（不许"备份完成"却藏一个坏 quota），且**不发清单**。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_sqlite(tmp_path / "app.db", "main")
    _seed_sqlite(data_dir / "quota_used.sqlite", "quota")

    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(tmp_path / "no_media"))
    monkeypatch.setattr(backup_data, "DATA_DIR", str(data_dir))
    # 主库那一次放行，附属那一次判坏 ⇒ 命中"附属失败"分支而不是主库分支
    monkeypatch.setattr(
        backup_data, "verify_sqlite", lambda p: (True, "ok") if Path(p).name == "app.db" else (False, "corrupt")
    )

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])
    printed = capsys.readouterr().out

    assert exit_code == 1, printed
    assert "备份完成" not in printed
    assert "附属产物" in printed
    assert not (tmp_path / "backup" / backup_data.MANIFEST_NAME).exists(), (
        "坏包里放一份看起来完整的清单=把没备份成洗成备份过了"
    )


def test_backup_fails_closed_when_extra_verification_raises(tmp_path, monkeypatch, capsys):
    """附属库的 verify **跑不动**（OSError / sqlite3.Error）⇒ 判 failed，与主库那条对称。

    旧版只给主库的 `verify_sqlite` 包了 try，附属那条是裸调用 ⇒ 一个打不开的 quota 会把整个脚本
    抛成 traceback：那既不是"备份完成"也不是"备份失败"，运维看到的是没有结论。
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_sqlite(tmp_path / "app.db", "main")
    _seed_sqlite(data_dir / "quota_used.sqlite", "quota")
    monkeypatch.setattr(backup_data, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(backup_data, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(tmp_path / "no_media"))

    def fail_verify(path):
        if Path(path).name == "app.db":
            return True, "ok"
        raise sqlite3.DatabaseError("cannot open")

    monkeypatch.setattr(backup_data, "verify_sqlite", fail_verify)

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])
    printed = capsys.readouterr().out

    assert exit_code == 1, printed
    assert "[Extras] ERROR quota_used.sqlite 恢复验证执行失败：cannot open" in printed, printed
    assert not (tmp_path / "backup" / backup_data.MANIFEST_NAME).exists()


def test_quota_guard_target_is_the_mapped_extra_source():
    """接线的另一半：守卫拿 QUOTA_DB 去比的"期望源"，必须就是附属映射算出的那份账本。

    期望值这里**故意独立写死**（`BACKEND/data/quota_used.sqlite`）—— 若两侧都写
    `os.path.join(DATA_DIR, ...)`，这条就退化成自己比自己、永远绿。它挡的是"接对了参数、
    但比的是另一个文件"（那样容器里要么误拒、要么该拒时不拒）。
    """
    assert backup_data.QUOTA_SOURCE == os.path.join(backup_data.BACKEND, "data", "quota_used.sqlite")
    assert os.path.basename(backup_data.QUOTA_SOURCE) == backup_data.EXTRA_SQLITE["quota_used.sqlite"]
