"""Запуск REST-сервера и демонстрация SQLite-операций."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

import uvicorn

from api import app


def demo() -> None:
    """Демонстрация прямых SQLite-операций."""
    from sqlite_ops import (
        books_never_read,
        books_per_publisher,
        export_csv,
        init_db,
        readers_same_city,
        seed_data,
        select_all_books_with_publishers,
        select_book_with_publisher,
    )

    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "demo.db")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        init_db(conn)
        seed_data(conn)

        print("=== INNER JOIN: книга #1 с издателем ===")
        print(select_book_with_publisher(conn, 1))

        print("\n=== LEFT JOIN: все книги (включая без издателя) ===")
        for row in select_all_books_with_publishers(conn):
            print(f"  {row['title']:30s} | {row['publisher_name'] or '—'}")

        print("\n=== GROUP BY + HAVING: издатели с ≥2 книгами ===")
        for row in books_per_publisher(conn):
            print(f"  {row['publisher']:20s} — {row['book_count']} книг(и)")

        print("\n=== Self-join: пары читателей из одного города ===")
        for row in readers_same_city(conn):
            print(f"  {row['reader_a']} & {row['reader_b']} — {row['city']}")

        print("\n=== LEFT JOIN + IS NULL: книги, которые никто не брал ===")
        for row in books_never_read(conn):
            print(f"  #{row['id']} {row['title']}")

        csv_path = os.path.join(td, "export.csv")
        count = export_csv(conn, csv_path)
        print(f"\n=== CSV-экспорт: {count} строк → {csv_path} ===")
        with open(csv_path, encoding="utf-8") as fh:
            print(fh.read())

        conn.close()


if __name__ == "__main__":
    if "--demo" in sys.argv or os.environ.get("MTP_HEADLESS") == "1":
        demo()
    else:
        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
