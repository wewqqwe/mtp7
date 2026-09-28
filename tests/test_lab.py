from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from api import app, configure
from sqlite_ops import delete_row, export_csv, init_db, insert_row, select_row

ROOT = Path(__file__).resolve().parents[1]


def test_select_delete_and_csv(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "library.db")
    init_db(conn)
    row_id = insert_row(conn, "Алгебра")
    assert select_row(conn, row_id) == "Алгебра"
    dest = tmp_path / "library.csv"
    export_csv(conn, dest)
    assert "Алгебра" in dest.read_text(encoding="utf-8")
    delete_row(conn, row_id)
    assert select_row(conn, row_id) is None
    conn.close()


def test_alembic_upgrade_creates_books(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    conn.close()
    assert "books" in names


def test_rest_create_then_read(tmp_path: Path) -> None:
    configure(f"sqlite:///{(tmp_path / 'books.db').as_posix()}")
    with TestClient(app) as client:
        created = client.post("/books", json={"title": "Теория графов"})
        assert created.status_code == 201
        body = created.json()
        fetched = client.get(f"/books/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Теория графов"
        assert fetched.json()["id"] == body["id"]
