from abc import ABC, abstractmethod
from typing import List, Optional, Generic, TypeVar, Dict, Any

T = TypeVar("T")


class BaseRepositoryInterface(ABC, Generic[T]):
    """Abstract Base Class for generic data repository operations."""

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        pass

    @abstractmethod
    async def create(self, item: T) -> T:
        pass

    @abstractmethod
    async def update(self, id: str, update_data: Dict[str, Any]) -> Optional[T]:
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass
