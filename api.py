"""REST API: книги и издатели (FastAPI + SQLAlchemy).

Полный CRUD для книг, создание/список издателей, фильтрация, статистика.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Book, Publisher

engine = None
SessionLocal = None


# ── Конфигурация ──────────────────────────────────────────────────────

def _default_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    path = Path(__file__).resolve().with_name("alina_books.db")
    return "sqlite:///" + path.as_posix()


def configure(url: str | None = None) -> None:
    """Инициализировать engine и создать таблицы."""
    global engine, SessionLocal
    chosen = url or _default_url()
    connect_args = {"check_same_thread": False} if chosen.startswith("sqlite") else {}
    engine = create_engine(chosen, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: сессия БД."""
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


app = FastAPI(title="Библиотека — ЛР №7, вариант 3", lifespan=lifespan)


# ── Pydantic-схемы ────────────────────────────────────────────────────

class PublisherIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)


class PublisherOut(BaseModel):
    id: int
    name: str
    city: str

    model_config = {"from_attributes": True}


class BookIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    year: int | None = Field(None, ge=1800, le=2100)
    publisher_id: int | None = None


class BookPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    year: int | None = Field(None, ge=1800, le=2100)
    publisher_id: int | None = None


class BookOut(BaseModel):
    id: int
    title: str
    year: int | None
    publisher_id: int | None
    publisher_name: str | None = None

    model_config = {"from_attributes": True}


class BookStats(BaseModel):
    total_books: int
    earliest_year: int | None
    latest_year: int | None
    publishers_count: int


# ── Вспомогательные ───────────────────────────────────────────────────

def _book_out(book: Book) -> BookOut:
    return BookOut(
        id=book.id,
        title=book.title,
        year=book.year,
        publisher_id=book.publisher_id,
        publisher_name=book.publisher.name if book.publisher else None,
    )


# ── Health ─────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Books: stats (до /{id}, чтобы не конфликтовал с path-параметром) ──

@app.get("/books/stats", response_model=BookStats)
def book_stats(db: Session = Depends(get_db)) -> BookStats:
    """Агрегированная статистика по книгам."""
    row = db.query(
        func.count(Book.id),
        func.min(Book.year),
        func.max(Book.year),
    ).one()
    pub_count = db.query(func.count(Publisher.id)).scalar() or 0
    return BookStats(
        total_books=row[0],
        earliest_year=row[1],
        latest_year=row[2],
        publishers_count=pub_count,
    )


# ── Books: CRUD ────────────────────────────────────────────────────────

@app.get("/books", response_model=list[BookOut])
def list_books(
    search: str | None = Query(None, description="Поиск по названию"),
    year_from: int | None = Query(None, ge=1800),
    year_to: int | None = Query(None, le=2100),
    publisher: str | None = Query(None, description="Имя издателя"),
    db: Session = Depends(get_db),
) -> list[BookOut]:
    """Список книг с опциональными фильтрами."""
    q = db.query(Book)
    if search:
        q = q.filter(Book.title.ilike(f"%{search}%"))
    if year_from is not None:
        q = q.filter(Book.year >= year_from)
    if year_to is not None:
        q = q.filter(Book.year <= year_to)
    if publisher:
        q = q.join(Publisher).filter(Publisher.name.ilike(f"%{publisher}%"))
    return [_book_out(b) for b in q.order_by(Book.id).all()]


@app.get("/books/{book_id}", response_model=BookOut)
def read_book(book_id: int, db: Session = Depends(get_db)) -> BookOut:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="книга не найдена")
    return _book_out(book)


@app.post("/books", status_code=201, response_model=BookOut)
def create_book(payload: BookIn, db: Session = Depends(get_db)) -> BookOut:
    if payload.publisher_id is not None:
        pub = db.get(Publisher, payload.publisher_id)
        if pub is None:
            raise HTTPException(status_code=422, detail="издатель не найден")
    book = Book(
        title=payload.title,
        year=payload.year,
        publisher_id=payload.publisher_id,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return _book_out(book)


@app.patch("/books/{book_id}", response_model=BookOut)
def update_book(
    book_id: int, payload: BookPatch, db: Session = Depends(get_db)
) -> BookOut:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="книга не найдена")
    update_data = payload.model_dump(exclude_unset=True)
    if "publisher_id" in update_data and update_data["publisher_id"] is not None:
        if db.get(Publisher, update_data["publisher_id"]) is None:
            raise HTTPException(status_code=422, detail="издатель не найден")
    for key, value in update_data.items():
        setattr(book, key, value)
    db.commit()
    db.refresh(book)
    return _book_out(book)


@app.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db)) -> None:
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="книга не найдена")
    db.delete(book)
    db.commit()


# ── Publishers ─────────────────────────────────────────────────────────

@app.get("/publishers", response_model=list[PublisherOut])
def list_publishers(db: Session = Depends(get_db)) -> list[PublisherOut]:
    return [
        PublisherOut.model_validate(p)
        for p in db.query(Publisher).order_by(Publisher.id).all()
    ]


@app.post("/publishers", status_code=201, response_model=PublisherOut)
def create_publisher(
    payload: PublisherIn, db: Session = Depends(get_db)
) -> PublisherOut:
    existing = db.query(Publisher).filter(Publisher.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=422, detail="издатель уже существует")
    pub = Publisher(name=payload.name, city=payload.city)
    db.add(pub)
    db.commit()
    db.refresh(pub)
    return PublisherOut.model_validate(pub)
