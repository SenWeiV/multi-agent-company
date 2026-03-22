from __future__ import annotations

from typing import Callable, Generic, Protocol, TypeVar

ModelT = TypeVar("ModelT")


class ModelStore(Protocol[ModelT]):
    def save(self, record: ModelT) -> ModelT: ...

    def get(self, record_id: str) -> ModelT | None: ...

    def list(self) -> list[ModelT]: ...


class InMemoryModelStore(Generic[ModelT]):
    def __init__(self, key_getter: Callable[[ModelT], str]) -> None:
        self._key_getter = key_getter
        self._records: dict[str, ModelT] = {}

    def save(self, record: ModelT) -> ModelT:
        self._records[self._key_getter(record)] = record
        return record

    def get(self, record_id: str) -> ModelT | None:
        return self._records.get(record_id)

    def list(self) -> list[ModelT]:
        return list(self._records.values())
