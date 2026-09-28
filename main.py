"""Запуск REST лабораторной №7."""

from __future__ import annotations

import os

import uvicorn

from api import app


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
