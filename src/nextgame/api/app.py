from __future__ import annotations
from fastapi import FastAPI
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="NextGame API", version="0.1.0")
    app.include_router(router)
    return app
