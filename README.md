# Лабораторная работа №7. Базы данных

**Осетрова Алина Романовна, группа 221141, вариант 3**

Дисциплина «Методы и технологии программирования» (часть 1).

## Задания варианта 3

| № | Задание | Уровень | Модуль |
|---|---------|---------|--------|
| 1 | Выбрать данные (SELECT) | Среднее | `sqlite_ops.py` |
| 2 | Удалить запись (DELETE) | Среднее | `sqlite_ops.py` |
| 3 | Экспорт CSV | Среднее | `sqlite_ops.py` |
| 4 | Миграции Alembic | Повышенное | `alembic/` |
| 5 | FastAPI + SQLAlchemy REST API | Повышенное | `api.py`, `models.py` |

## Предметная область

Предметная область — **библиотека**: издательства выпускают книги, читатели
берут книги на абонемент. Данные хранятся в четырёх таблицах.

### ER-диаграмма

```
publishers              books                loans              readers
┌──────────┐       ┌──────────────┐     ┌──────────────┐    ┌──────────┐
│ id  PK   │──1:N──│ id  PK       │──1:N│ id  PK       │N:1─│ id  PK   │
│ name     │       │ title        │     │ book_id  FK  │    │ name     │
│ city     │       │ year         │     │ reader_id FK │    │ city     │
└──────────┘       │ publisher_id │     │ borrowed_date│    └──────────┘
                   │   FK → pubs  │     │ returned_date│
                   └──────────────┘     └──────────────┘
```

## Структура проекта

```
mtp7/
├── sqlite_ops.py        # Прямой SQLite: SELECT, JOIN, GROUP BY, DELETE, CSV
├── models.py            # SQLAlchemy ORM-модели (Publisher, Book, Reader)
├── api.py               # FastAPI REST — CRUD книг и издателей
├── main.py              # Точка входа: сервер или --demo
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_create_tables.py    # publishers + books (с year и FK)
│       └── 0002_add_readers.py      # CREATE TABLE readers
├── tests/
│   └── test_lab.py      # 25 тестов: sqlite, alembic, REST
├── requirements.txt
└── README.md
```

## Описание решений

### Средние задания (`sqlite_ops.py`)

Работа ведётся напрямую через `sqlite3`, без ORM.

- **SELECT** — выбор книги по id (`select_row`), INNER JOIN с издателем
  (`select_book_with_publisher`), LEFT JOIN всех книг
  (`select_all_books_with_publishers`), GROUP BY + HAVING
  (`books_per_publisher` — издатели с ≥2 книгами), self-join читателей
  из одного города (`readers_same_city`), LEFT JOIN + IS NULL — книги,
  которые никто не брал (`books_never_read`).
- **DELETE** — `delete_row` удаляет книгу и возвращает `True`/`False` в
  зависимости от того, существовала ли запись.
- **CSV** — `export_csv` выгружает книги с LEFT JOIN на издателя, записывая
  `id, title, publisher_name, year`. Возвращает количество строк.

### Повышенные задания

#### Alembic (`alembic/versions/`)

Две миграции:

1. `0001_create_tables` — создаёт `publishers` и `books` (с FK и колонкой `year`).
2. `0002_add_readers` — создаёт таблицу `readers` — демонстрирует
   реальную инкрементальную эволюцию схемы.

Обе поддерживают `downgrade` до `base`.

#### REST API (`api.py` + `models.py`)

FastAPI-приложение с полным CRUD:

| Метод | Путь | Описание | Код |
|-------|------|----------|-----|
| GET | `/health` | Проверка живости | 200 |
| GET | `/books/stats` | Агрегированная статистика | 200 |
| GET | `/books` | Список с фильтрами `search`, `year_from`, `year_to`, `publisher` | 200 |
| GET | `/books/{id}` | Одна книга с именем издателя | 200 / 404 |
| POST | `/books` | Создать книгу | 201 / 422 |
| PATCH | `/books/{id}` | Частичное обновление | 200 / 404 / 422 |
| DELETE | `/books/{id}` | Удалить | 204 / 404 |
| GET | `/publishers` | Список издателей | 200 |
| POST | `/publishers` | Создать издателя | 201 / 422 |

Обработка ошибок: 404 для несуществующих ресурсов, 422 для невалидных
данных (пустой заголовок, несуществующий publisher_id, дубликат издателя).

## Запуск

```bash
# REST-сервер
python main.py

# Демонстрация SQLite-операций
python main.py --demo

# Тесты
python -m pytest tests/test_lab.py -v

# Alembic
alembic upgrade head
alembic downgrade base
```
