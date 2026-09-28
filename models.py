"""SQLAlchemy-модели предметной области «Библиотека».

Связи: Publisher 1→N Book.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    city: Mapped[str] = mapped_column(String(100))

    books: Mapped[list[Book]] = relationship(back_populates="publisher")

    def __repr__(self) -> str:
        return f"Publisher(id={self.id!r}, name={self.name!r})"


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1800 AND 2100", name="ck_books_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishers.id"), nullable=True
    )

    publisher: Mapped[Publisher | None] = relationship(back_populates="books")

    def __repr__(self) -> str:
        return f"Book(id={self.id!r}, title={self.title!r})"


class Reader(Base):
    __tablename__ = "readers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"Reader(id={self.id!r}, name={self.name!r})"
