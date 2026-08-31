import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.core.security import get_password_hash
from app.schemas.user import UserResponse, UserCreate, UserRole, UserUpdate


class UserRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[UserResponse]:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[UserResponse]:
        pass

    @abstractmethod
    async def create(self, user_create: UserCreate) -> UserResponse:
        pass

    @abstractmethod
    async def get_password_hash(self, email: str) -> Optional[str]:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        pass

    @abstractmethod
    async def update(self, user_id: str, update_data: UserUpdate) -> Optional[UserResponse]:
        pass

    @abstractmethod
    async def count(self) -> int:
        pass


class InMemoryUserRepository(UserRepositoryInterface):
    """In-memory User Repository implementation for initial backend development."""

    def __init__(self):
        self._users: Dict[str, Dict[str, Any]] = {}
        self._email_to_id: Dict[str, str] = {}
        self._seed_default_users()

    def _seed_default_users(self):
        # Admin User
        admin_id = "user-admin-001"
        admin_email = "admin@crimelens.ai"
        self._users[admin_id] = {
            "id": admin_id,
            "email": admin_email,
            "password_hash": get_password_hash("AdminSecret123!"),
            "full_name": "Chief Investigator Admin",
            "role": UserRole.ADMIN,
            "badge_number": "BADGE-001",
            "agency": "CrimeLens AI HQ",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self._email_to_id[admin_email.lower()] = admin_id

        # Investigator User
        inv_id = "user-inv-002"
        inv_email = "investigator@crimelens.ai"
        self._users[inv_id] = {
            "id": inv_id,
            "email": inv_email,
            "password_hash": get_password_hash("Investigator123!"),
            "full_name": "Senior Investigator Agent",
            "role": UserRole.INVESTIGATOR,
            "badge_number": "BADGE-002",
            "agency": "CrimeLens AI Division",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self._email_to_id[inv_email.lower()] = inv_id

    async def get_by_id(self, user_id: str) -> Optional[UserResponse]:
        user_dict = self._users.get(user_id)
        if not user_dict:
            return None
        return UserResponse(**user_dict)

    async def get_by_email(self, email: str) -> Optional[UserResponse]:
        user_id = self._email_to_id.get(email.lower())
        if not user_id:
            return None
        return await self.get_by_id(user_id)

    async def get_password_hash(self, email: str) -> Optional[str]:
        user_id = self._email_to_id.get(email.lower())
        if not user_id:
            return None
        user_dict = self._users.get(user_id)
        return user_dict["password_hash"] if user_dict else None

    async def create(self, user_create: UserCreate) -> UserResponse:
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        user_dict = {
            "id": user_id,
            "email": user_create.email.lower(),
            "password_hash": get_password_hash(user_create.password),
            "full_name": user_create.full_name,
            "role": user_create.role,
            "badge_number": user_create.badge_number,
            "agency": user_create.agency or "CrimeLens AI Agency",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        self._users[user_id] = user_dict
        self._email_to_id[user_create.email.lower()] = user_id
        return UserResponse(**user_dict)

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        all_users = [UserResponse(**u) for u in self._users.values()]
        return all_users[skip : skip + limit]

    async def update(self, user_id: str, update_data: UserUpdate) -> Optional[UserResponse]:
        user_dict = self._users.get(user_id)
        if not user_dict:
            return None
        
        data_to_update = update_data.model_dump(exclude_unset=True)
        for k, v in data_to_update.items():
            if v is not None:
                user_dict[k] = v
        user_dict["updated_at"] = datetime.now(timezone.utc)
        return UserResponse(**user_dict)

    async def count(self) -> int:
        return len(self._users)


user_repository = InMemoryUserRepository()
