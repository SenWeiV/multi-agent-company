from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel
from psycopg import connect, sql
from psycopg.types.json import Jsonb

from app.store.base import ModelStore

ModelT = TypeVar("ModelT", bound=BaseModel)


class PostgresJsonStore(Generic[ModelT], ModelStore[ModelT]):
    def __init__(self, model_cls: type[ModelT], key_field: str, table_name: str, dsn: str) -> None:
        self._model_cls = model_cls
        self._key_field = key_field
        self._table_name = table_name
        self._dsn = dsn
        self._ensure_table()

    def save(self, record: ModelT) -> ModelT:
        record_id = getattr(record, self._key_field)
        payload = record.model_dump(mode="json")
        with connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {table} (entity_id, payload)
                        VALUES (%s, %s)
                        ON CONFLICT (entity_id)
                        DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                        """
                    ).format(table=sql.Identifier(self._table_name)),
                    (record_id, Jsonb(payload)),
                )
        return record

    def get(self, record_id: str) -> ModelT | None:
        with connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT payload FROM {table} WHERE entity_id = %s").format(
                        table=sql.Identifier(self._table_name)
                    ),
                    (record_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._model_cls.model_validate(row[0])

    def list(self) -> list[ModelT]:
        with connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT payload FROM {table} ORDER BY updated_at ASC").format(
                        table=sql.Identifier(self._table_name)
                    )
                )
                rows = cur.fetchall()
        return [self._model_cls.model_validate(row[0]) for row in rows]

    def _ensure_table(self) -> None:
        with connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {table} (
                            entity_id TEXT PRIMARY KEY,
                            payload JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    ).format(table=sql.Identifier(self._table_name))
                )
