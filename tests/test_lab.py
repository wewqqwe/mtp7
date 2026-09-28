"""Тесты лабораторной работы №7.

Группы:
- SQLite: init, seed, SELECT, JOIN, GROUP BY, HAVING, self-join, DELETE, CSV
- Alembic: upgrade, downgrade, проверка таблиц/колонок
- REST API: health, CRUD, фильтры, 404, 422, stats
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from api import app, configure
from sqlite_ops import (
    books_never_read,
    books_per_publisher,
    delete_row,
    export_csv,
    init_db,
    readers_same_city,
    seed_data,
    select_all_books_with_publishers,
    select_book_with_publisher,
    select_row,
)

ROOT = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════════
#  SQLite
# ══════════════════════════════════════════════════════════════════════

def _seeded_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "lib.db")
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    seed_data(conn)
    return conn


def test_seed_data_counts(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    assert conn.execute("SELECT COUNT(*) FROM publishers").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 7
    assert conn.execute("SELECT COUNT(*) FROM readers").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0] == 5
    conn.close()


def test_select_row_existing(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    row = select_row(conn, 1)
    assert row is not None
    assert row["title"] == "Алгебра и начала анализа"
    assert row["year"] == 2019
    conn.close()


def test_select_row_missing(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    assert select_row(conn, 999) is None
    conn.close()


def test_inner_join_book_with_publisher(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    row = select_book_with_publisher(conn, 1)
    assert row is not None
    assert row["publisher_name"] == "Наука"
    # Книга без издателя — INNER JOIN не вернёт
    assert select_book_with_publisher(conn, 7) is None
    conn.close()


def test_left_join_all_books(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    rows = select_all_books_with_publishers(conn)
    assert len(rows) == 7
    orphan = next(r for r in rows if r["title"] == "Философия Java")
    assert orphan["publisher_name"] is None
    named = next(r for r in rows if r["title"] == "Базы данных")
    assert named["publisher_name"] == "Питер"
    conn.close()


def test_group_by_having(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    stats = books_per_publisher(conn)
    # Питер и БХВ-Петербург — по 2 книги каждый
    assert len(stats) >= 2
    names = {s["publisher"] for s in stats}
    assert "Питер" in names
    assert "БХВ-Петербург" in names
    assert all(s["book_count"] >= 2 for s in stats)
    conn.close()


def test_self_join_readers_same_city(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    pairs = readers_same_city(conn)
    assert len(pairs) > 0
    # У нас: Казань — (Петрова, Козлова); Москва — (Иванов, Сидоров)
    cities = {p["city"] for p in pairs}
    assert "Москва" in cities
    assert "Казань" in cities
    conn.close()


def test_books_never_read(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    never = books_never_read(conn)
    titles = {b["title"] for b in never}
    assert "Дискретная математика" in titles
    assert "Философия Java" in titles
    # Книга 1 была выдана — не должна попасть
    assert "Алгебра и начала анализа" not in titles
    conn.close()


def test_delete_row_returns_flag(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    # id=6 — «Дискретная математика», без выдач → можно удалить
    assert delete_row(conn, 6) is True
    assert select_row(conn, 6) is None
    assert delete_row(conn, 6) is False
    conn.close()


def test_export_csv_with_join(tmp_path: Path) -> None:
    conn = _seeded_conn(tmp_path)
    dest = tmp_path / "export.csv"
    count = export_csv(conn, dest)
    assert count == 7
    with dest.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert len(rows) == 7
    assert rows[0]["publisher_name"] == "Наука"
    orphan = next(r for r in rows if r["title"] == "Философия Java")
    assert orphan["publisher_name"] == ""
    conn.close()


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "init.db")
    init_db(conn)
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert tables >= {"publishers", "books", "readers", "loans"}
    conn.close()


def test_self_join_no_mirror_pairs(tmp_path: Path) -> None:
    """Проверить, что self-join не возвращает зеркальные пары (A,B) и (B,A)."""
    conn = _seeded_conn(tmp_path)
    pairs = readers_same_city(conn)
    seen: set[tuple[str, str]] = set()
    for p in pairs:
        key = (p["reader_a"], p["reader_b"])
        mirror = (p["reader_b"], p["reader_a"])
        assert mirror not in seen, f"зеркальная пара: {key}"
        seen.add(key)
    conn.close()


def test_foreign_key_enforcement(tmp_path: Path) -> None:
    """FK constraint не позволяет вставить книгу с несуществующим publisher_id."""
    conn = sqlite3.connect(tmp_path / "fk.db")
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    try:
        conn.execute(
            "INSERT INTO books (title, year, publisher_id) VALUES (?, ?, ?)",
            ("Тест", 2020, 999),
        )
        conn.commit()
        assert False, "FK constraint должен был сработать"
    except sqlite3.IntegrityError:
        pass
    conn.close()


def test_csv_header_columns(tmp_path: Path) -> None:
    """Проверить, что CSV-заголовок содержит правильные колонки."""
    conn = _seeded_conn(tmp_path)
    dest = tmp_path / "hdr.csv"
    export_csv(conn, dest)
    with dest.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == ["id", "title", "publisher_name", "year"]
    conn.close()


# ══════════════════════════════════════════════════════════════════════
#  Alembic
# ══════════════════════════════════════════════════════════════════════

def _alembic_cfg(tmp_path: Path) -> Config:
    db_path = tmp_path / "alembic_test.db"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def test_alembic_upgrade_creates_tables(tmp_path: Path) -> None:
    cfg = _alembic_cfg(tmp_path)
    command.upgrade(cfg, "head")
    db_path = tmp_path / "alembic_test.db"
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "publishers" in tables
    assert "books" in tables
    assert "readers" in tables  # из миграции 0002
    # Проверить колонки books (year включён в 0001)
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(books)")
    }
    assert "year" in cols
    assert "title" in cols
    assert "publisher_id" in cols
    # Проверить колонки readers
    reader_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(readers)")
    }
    assert "name" in reader_cols
    assert "city" in reader_cols
    conn.close()


def test_alembic_downgrade_to_base(tmp_path: Path) -> None:
    cfg = _alembic_cfg(tmp_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    db_path = tmp_path / "alembic_test.db"
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "books" not in tables
    assert "publishers" not in tables
    assert "readers" not in tables
    conn.close()


def test_alembic_partial_upgrade_0001(tmp_path: Path) -> None:
    """Промежуточная миграция: после 0001 есть publishers+books, но нет readers."""
    cfg = _alembic_cfg(tmp_path)
    command.upgrade(cfg, "0001")
    db_path = tmp_path / "alembic_test.db"
    conn = sqlite3.connect(db_path)
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "publishers" in tables
    assert "books" in tables
    assert "readers" not in tables
    conn.close()


# ══════════════════════════════════════════════════════════════════════
#  REST API
# ══════════════════════════════════════════════════════════════════════

def _client(tmp_path: Path) -> TestClient:
    configure(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    return TestClient(app)


def test_health(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_rest_crud_books(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # Создать издателя
    pub = client.post("/publishers", json={"name": "Наука", "city": "Москва"})
    assert pub.status_code == 201
    pub_id = pub.json()["id"]

    # Создать книгу
    created = client.post(
        "/books",
        json={"title": "Теория графов", "year": 2020, "publisher_id": pub_id},
    )
    assert created.status_code == 201
    book_id = created.json()["id"]
    assert created.json()["publisher_name"] == "Наука"

    # Прочитать
    fetched = client.get(f"/books/{book_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Теория графов"

    # Обновить (PATCH)
    patched = client.patch(f"/books/{book_id}", json={"year": 2021})
    assert patched.status_code == 200
    assert patched.json()["year"] == 2021
    assert patched.json()["title"] == "Теория графов"  # не изменилось

    # Удалить
    deleted = client.delete(f"/books/{book_id}")
    assert deleted.status_code == 204
    assert client.get(f"/books/{book_id}").status_code == 404


def test_rest_404_on_missing(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/books/999").status_code == 404
    assert client.patch("/books/999", json={"year": 2020}).status_code == 404
    assert client.delete("/books/999").status_code == 404


def test_rest_422_invalid_publisher(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/books",
        json={"title": "Тест", "publisher_id": 999},
    )
    assert resp.status_code == 422


def test_rest_422_empty_title(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/books", json={"title": ""})
    assert resp.status_code == 422


def test_rest_filters(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pub = client.post("/publishers", json={"name": "МГУ", "city": "Москва"})
    pub_id = pub.json()["id"]
    client.post("/books", json={"title": "Книга A", "year": 2018, "publisher_id": pub_id})
    client.post("/books", json={"title": "Книга B", "year": 2022, "publisher_id": pub_id})
    client.post("/books", json={"title": "Другая C", "year": 2019})

    # Фильтр по названию
    resp = client.get("/books", params={"search": "Книга"})
    assert len(resp.json()) == 2

    # Фильтр по году
    resp = client.get("/books", params={"year_from": 2020})
    assert all(b["year"] >= 2020 for b in resp.json())

    # Фильтр по издателю
    resp = client.get("/books", params={"publisher": "МГУ"})
    assert len(resp.json()) == 2


def test_rest_duplicate_publisher(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/publishers", json={"name": "Наука", "city": "Москва"})
    dup = client.post("/publishers", json={"name": "Наука", "city": "Казань"})
    assert dup.status_code == 422


def test_rest_stats(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/publishers", json={"name": "Тест", "city": "СПб"})
    client.post("/books", json={"title": "A", "year": 2010})
    client.post("/books", json={"title": "B", "year": 2023})
    resp = client.get("/books/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_books"] == 2
    assert data["earliest_year"] == 2010
    assert data["latest_year"] == 2023
    assert data["publishers_count"] == 1


def test_rest_publishers_list(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/publishers", json={"name": "Наука", "city": "Москва"})
    client.post("/publishers", json={"name": "Питер", "city": "СПб"})
    resp = client.get("/publishers")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"Наука", "Питер"}


def test_rest_book_without_publisher(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/books", json={"title": "Сирота", "year": 2020})
    assert resp.status_code == 201
    assert resp.json()["publisher_name"] is None
    assert resp.json()["publisher_id"] is None


def test_rest_patch_publisher_id(tmp_path: Path) -> None:
    """PATCH: привязать книгу к издателю после создания."""
    client = _client(tmp_path)
    book = client.post("/books", json={"title": "Книга"}).json()
    pub = client.post("/publishers", json={"name": "МГУ", "city": "Москва"}).json()
    patched = client.patch(f"/books/{book['id']}", json={"publisher_id": pub["id"]})
    assert patched.status_code == 200
    assert patched.json()["publisher_name"] == "МГУ"


def test_rest_year_range_filter(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/books", json={"title": "Старая", "year": 1990})
    client.post("/books", json={"title": "Средняя", "year": 2010})
    client.post("/books", json={"title": "Новая", "year": 2023})
    resp = client.get("/books", params={"year_from": 2000, "year_to": 2015})
    titles = [b["title"] for b in resp.json()]
    assert titles == ["Средняя"]
