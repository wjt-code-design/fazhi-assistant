"""Fail-closed contracts for the production backup helper."""

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


def _seed_sqlite(path):
    """建一个真能打开的最小 SQLite 库（用 backup API 复制它时需要合法的页结构）。"""
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        con.execute("INSERT INTO t (v) VALUES ('x')")
    con.close()


def test_backup_also_covers_quota_store_container_db_and_media(tmp_path, monkeypatch, capsys):
    """S4：备份面此前**只有** app.db + chroma —— quota 记账、容器侧 app.db、media 全在任何备份之外。

    这三件都是实测缺口（`backup_data.main()` 旧版只写三样东西）：
    `backend/data/quota_used.sqlite`（谁烧了多少 token 的唯一账本）、
    `backend/data/app.db`（compose 挂进容器的那份库）、`backend/media`（上传件）。
    """
    src = tmp_path / "app.db"
    _seed_sqlite(src)
    quota = tmp_path / "quota_used.sqlite"
    _seed_sqlite(quota)
    data_app = tmp_path / "data_app.db"
    _seed_sqlite(data_app)
    media = tmp_path / "media"
    (media / "sub").mkdir(parents=True)
    (media / "sub" / "a.png").write_bytes(b"\x89PNG-7")

    monkeypatch.setattr(backup_data, "DB_PATH", str(src))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(
        backup_data, "EXTRA_SQLITE", {"quota_used.sqlite": str(quota), "data_app.db": str(data_app)}, raising=False
    )
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(media), raising=False)

    out = tmp_path / "backup"
    exit_code = backup_data.main(["--out", str(out), "--skip-chroma"])

    assert exit_code == 0, capsys.readouterr().out
    assert (out / "quota_used.sqlite").is_file(), "quota 账本没进备份包"
    assert (out / "data_app.db").is_file(), "容器侧 app.db 没进备份包"
    assert (out / "media" / "sub" / "a.png").read_bytes() == b"\x89PNG-7"
    # 备份的是**可读的库**而不是空文件：能开、且行数在
    con = sqlite3.connect(f"file:{(out / 'quota_used.sqlite').as_posix()}?mode=ro", uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        con.close()


def test_backup_tolerates_absent_extras_and_says_so(tmp_path, monkeypatch, capsys):
    """缺件不该让整个备份失败（干净机器上可能就没有 media/容器库），但必须**说出来**。"""
    src = tmp_path / "app.db"
    _seed_sqlite(src)
    monkeypatch.setattr(backup_data, "DB_PATH", str(src))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(
        backup_data,
        "EXTRA_SQLITE",
        {"quota_used.sqlite": str(tmp_path / "nope.sqlite")},
        raising=False,
    )
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(tmp_path / "no_media"), raising=False)

    out = tmp_path / "backup"
    exit_code = backup_data.main(["--out", str(out), "--skip-chroma"])
    printed = capsys.readouterr().out

    assert exit_code == 0, printed
    assert not (out / "quota_used.sqlite").exists()
    # 断言必须指向**具体缺的是哪件**——旧实现里 `[Chroma] 已按显式 --skip-chroma 跳过`
    # 也含"跳过"二字，只断言"跳过"会得到一条假绿（本票第一轮就中招）。
    assert "quota_used.sqlite" in printed, printed
    assert "media" in printed, printed


def test_backup_fails_closed_when_extra_sqlite_is_corrupt(tmp_path, monkeypatch, capsys):
    """附属库校验不过 ⇒ 整个备份判失败（不许"备份完成"却藏一个坏 quota）。"""
    src = tmp_path / "app.db"
    _seed_sqlite(src)
    quota = tmp_path / "quota_used.sqlite"
    _seed_sqlite(quota)

    monkeypatch.setattr(backup_data, "DB_PATH", str(src))
    monkeypatch.setattr(backup_data, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(backup_data, "MEDIA_DIR", str(tmp_path / "no_media"), raising=False)
    monkeypatch.setattr(backup_data, "EXTRA_SQLITE", {"quota_used.sqlite": str(quota)}, raising=False)
    # 主库那一次放行，附属那一次判坏 ⇒ 命中"附属失败"分支而不是主库分支
    monkeypatch.setattr(
        backup_data, "verify_sqlite", lambda p: (True, "ok") if Path(p).name == "app.db" else (False, "corrupt")
    )

    exit_code = backup_data.main(["--out", str(tmp_path / "backup"), "--skip-chroma"])
    printed = capsys.readouterr().out

    assert exit_code == 1, printed
    assert "备份完成" not in printed
    assert "附属产物" in printed
