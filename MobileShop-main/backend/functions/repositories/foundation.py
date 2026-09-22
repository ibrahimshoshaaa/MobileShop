from dataclasses import replace
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")

class InMemoryRepository(Generic[T]):
    """Deterministic repository for Phase 1 tests; Firebase adapter will implement the same boundary."""
    def __init__(self):
        self._items: dict[str, T] = {}
        self._lock = RLock()

    def get(self, item_id: str) -> T | None:
        with self._lock:
            return self._items.get(item_id)

    def create(self, item_id: str, item: T) -> T:
        with self._lock:
            if item_id in self._items:
                raise ValueError("ALREADY_EXISTS")
            self._items[item_id] = item
            return item

    def update(self, item_id: str, item: T) -> T:
        with self._lock:
            if item_id not in self._items:
                raise KeyError("NOT_FOUND")
            self._items[item_id] = item
            return item

    def all(self) -> list[T]:
        with self._lock:
            return list(self._items.values())
