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
