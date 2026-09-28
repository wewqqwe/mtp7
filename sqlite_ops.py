"""Прямая работа с SQLite: SELECT, JOIN, GROUP BY, DELETE, CSV-экспорт.

Предметная область — библиотека: издатели, книги, читатели, выдачи.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    """Создать таблицы publishers, books, readers, loans с FK и CHECK."""
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS publishers (
            id   INTEGER PRIMARY KEY,
            name TEXT    NOT NULL UNIQUE,
            city TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS books (
            id           INTEGER PRIMARY KEY,
            title        TEXT    NOT NULL,
            year         INTEGER CHECK(year BETWEEN 1800 AND 2100),
            publisher_id INTEGER,
            FOREIGN KEY (publisher_id) REFERENCES publishers(id)
        );

        CREATE TABLE IF NOT EXISTS readers (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS loans (
            id            INTEGER PRIMARY KEY,
            book_id       INTEGER NOT NULL,
            reader_id     INTEGER NOT NULL,
            borrowed_date TEXT    NOT NULL,
            returned_date TEXT,
            FOREIGN KEY (book_id)   REFERENCES books(id),
            FOREIGN KEY (reader_id) REFERENCES readers(id)
        );
        """
    )


def seed_data(conn: sqlite3.Connection) -> None:
    """Заполнить БД тестовыми данными.

    Намеренно создаются «сироты»: издатель без книг, книга без издателя,
    книги, которые никто не брал.
    """
    conn.executescript("PRAGMA foreign_keys = ON;")

    publishers = [
        ("Наука", "Москва"),
        ("Питер", "Санкт-Петербург"),
        ("БХВ-Петербург", "Санкт-Петербург"),
        ("Лань", "Санкт-Петербург"),
        ("Мир", "Москва"),           # издатель без книг — сирота
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO publishers (name, city) VALUES (?, ?)",
        publishers,
    )

    books = [
        ("Алгебра и начала анализа", 2019, 1),
        ("Базы данных", 2021, 2),
        ("Сети ЭВМ", 2020, 2),
        ("Компиляторы", 2018, 3),
        ("Алгоритмы на Python", 2022, 3),
        ("Дискретная математика", 2017, 4),
        ("Философия Java", 2015, None),   # книга без издателя — сирота
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO books (title, year, publisher_id) VALUES (?, ?, ?)",
        books,
    )

    readers = [
        ("Иванов И. И.", "Москва"),
        ("Петрова А. С.", "Казань"),
        ("Сидоров М. В.", "Москва"),
        ("Козлова Е. Н.", "Казань"),
        ("Орлов Д. А.", "Новосибирск"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO readers (name, city) VALUES (?, ?)",
        readers,
    )

    # Выдачи: часть книг выдана, часть — нет (books id=6,7 никто не брал)
    loans = [
        (1, 1, "2025-09-01", "2025-09-15"),
        (2, 2, "2025-09-05", None),
        (3, 3, "2025-09-10", "2025-09-20"),
        (4, 1, "2025-09-12", None),
        (5, 4, "2025-09-14", "2025-09-28"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO loans (book_id, reader_id, borrowed_date, returned_date) "
        "VALUES (?, ?, ?, ?)",
        loans,
    )
    conn.commit()


# ── SELECT ─────────────────────────────────────────────────────────────

def select_row(conn: sqlite3.Connection, book_id: int) -> dict | None:
    """Выбрать книгу по id. Возвращает dict или None."""
    row = conn.execute(
        "SELECT id, title, year, publisher_id FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "title": row[1], "year": row[2], "publisher_id": row[3]}


def select_book_with_publisher(
    conn: sqlite3.Connection, book_id: int
) -> dict | None:
    """INNER JOIN: книга + имя издателя."""
    row = conn.execute(
        """
        SELECT b.id, b.title, b.year, p.name AS publisher_name
        FROM books b
        INNER JOIN publishers p ON b.publisher_id = p.id
        WHERE b.id = ?
        """,
        (book_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "year": row[2],
        "publisher_name": row[3],
    }


def select_all_books_with_publishers(conn: sqlite3.Connection) -> list[dict]:
    """LEFT JOIN: все книги, включая те, у которых нет издателя."""
    rows = conn.execute(
        """
        SELECT b.id, b.title, b.year, p.name AS publisher_name
        FROM books b
        LEFT JOIN publishers p ON b.publisher_id = p.id
        ORDER BY b.id
        """
    ).fetchall()
    return [
        {"id": r[0], "title": r[1], "year": r[2], "publisher_name": r[3]}
        for r in rows
    ]


def books_per_publisher(conn: sqlite3.Connection) -> list[dict]:
    """GROUP BY + HAVING: издатели с двумя и более книгами."""
    rows = conn.execute(
        """
        SELECT p.name, COUNT(*) AS cnt
        FROM books b
        JOIN publishers p ON b.publisher_id = p.id
        GROUP BY p.id
        HAVING cnt >= 2
        ORDER BY cnt DESC
        """
    ).fetchall()
    return [{"publisher": r[0], "book_count": r[1]} for r in rows]


def readers_same_city(conn: sqlite3.Connection) -> list[dict]:
    """Self-join: пары читателей из одного города (без зеркал).

    Условие a.id < b.id исключает дубликаты (A,B) и (B,A).
    """
    rows = conn.execute(
        """
        SELECT a.name AS reader_a, b.name AS reader_b, a.city
        FROM readers a
        JOIN readers b ON a.city = b.city AND a.id < b.id
        ORDER BY a.city, a.name
        """
    ).fetchall()
    return [
        {"reader_a": r[0], "reader_b": r[1], "city": r[2]}
        for r in rows
    ]


def books_never_read(conn: sqlite3.Connection) -> list[dict]:
    """LEFT JOIN + IS NULL: книги, которые ни разу не были выданы."""
    rows = conn.execute(
        """
        SELECT b.id, b.title
        FROM books b
        LEFT JOIN loans l ON b.id = l.book_id
        WHERE l.id IS NULL
        ORDER BY b.id
        """
    ).fetchall()
    return [{"id": r[0], "title": r[1]} for r in rows]


# ── DELETE ─────────────────────────────────────────────────────────────

def delete_row(conn: sqlite3.Connection, book_id: int) -> bool:
    """Удалить книгу. Возвращает True если строка существовала."""
    cur = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    return cur.rowcount > 0


# ── CSV ────────────────────────────────────────────────────────────────

def export_csv(conn: sqlite3.Connection, dest_path: str | Path) -> int:
    """Экспорт книг с LEFT JOIN на издателя в CSV. Возвращает кол-во строк."""
    rows = conn.execute(
        """
        SELECT b.id, b.title, COALESCE(p.name, '') AS publisher_name, b.year
        FROM books b
        LEFT JOIN publishers p ON b.publisher_id = p.id
        ORDER BY b.id
        """
    ).fetchall()
    with Path(dest_path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "title", "publisher_name", "year"])
        writer.writerows(rows)
    return len(rows)
