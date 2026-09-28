"""Выбор, удаление и CSV для таблицы library."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS library ("
        "id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
    )
    conn.commit()


def insert_row(conn: sqlite3.Connection, title: str) -> int:
    cur = conn.execute("INSERT INTO library (title) VALUES (?)", (title,))
    conn.commit()
    return int(cur.lastrowid)


def select_row(conn: sqlite3.Connection, row_id: int) -> str | None:
    row = conn.execute(
        "SELECT title FROM library WHERE id = ?", (row_id,)
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def delete_row(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("DELETE FROM library WHERE id = ?", (row_id,))
    conn.commit()


def export_csv(conn: sqlite3.Connection, dest_path: str | Path) -> None:
    rows = conn.execute("SELECT id, title FROM library ORDER BY id").fetchall()
    with Path(dest_path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "title"])
        writer.writerows(rows)
