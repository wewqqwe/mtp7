"""REST FastAPI + SQLAlchemy: создать книгу и прочитать её."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Book

engine = None
SessionLocal = None


def _default_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    path = Path(__file__).resolve().with_name("alina_books.db")
    return "sqlite:///" + path.as_posix()


def configure(url: str | None = None) -> None:
    global engine, SessionLocal
    chosen = url or _default_url()
    connect_args = {"check_same_thread": False} if chosen.startswith("sqlite") else {}
    engine = create_engine(chosen, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    if SessionLocal is None:
        configure()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if engine is None:
        configure()
    else:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Книги Алины, вариант 3", lifespan=lifespan)


class BookIn(BaseModel):
    title: str


@app.post("/books", status_code=201)
def create_book(payload: BookIn, db: Session = Depends(get_db)) -> dict[str, int | str]:
    row = Book(title=payload.title)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": int(row.id), "title": row.title}


@app.get("/books/{book_id}")
def read_book(book_id: int, db: Session = Depends(get_db)) -> dict[str, int | str]:
    row = db.get(Book, book_id)
    if row is None:
        raise HTTPException(status_code=404, detail="книга не найдена")
    return {"id": int(row.id), "title": row.title}
