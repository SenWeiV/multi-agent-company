from __future__ import annotations

from pydantic import BaseModel

from app.core.config import get_settings
from app.store.base import InMemoryModelStore, ModelStore


def build_model_store(model_cls: type[BaseModel], key_field: str, table_name: str) -> ModelStore:
    settings = get_settings()
    backend = settings.state_store_backend.lower()

    if backend == "postgres":
        from app.store.postgres import PostgresJsonStore

        return PostgresJsonStore(
            model_cls=model_cls,
            key_field=key_field,
            table_name=table_name,
            dsn=settings.postgres_dsn,
        )

    return InMemoryModelStore(lambda record: getattr(record, key_field))
