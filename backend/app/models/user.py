"""User account model."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.records import _now


@dataclass
class UserRecord:
    id: str
    email: str
    name: str
    hashed_password: str
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "hashed_password": self.hashed_password,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "UserRecord":
        return UserRecord(
            id=d["id"],
            email=d["email"],
            name=d["name"],
            hashed_password=d["hashed_password"],
            created_at=d.get("created_at", _now()),
            updated_at=d.get("updated_at", _now()),
        )
