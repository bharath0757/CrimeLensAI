from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BaseRepositoryInterface(ABC, Generic[T]):
    """Abstract Base Class for generic data repository operations."""

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        pass

    @abstractmethod
    async def create(self, item: T) -> T:
        pass

    @abstractmethod
    async def update(self, id: str, update_data: dict[str, Any]) -> T | None:
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass
