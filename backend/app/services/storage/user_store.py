"""User store — persists accounts to the same SQL database as documents."""

from __future__ import annotations

import threading
import uuid

from app.core.config import Settings
from app.models.records import _now
from app.models.user import UserRecord


class UserStore:
    """Thread-safe SQL-backed user account store."""

    def __init__(self, settings: Settings) -> None:
        from sqlalchemy import (
            Column,
            MetaData,
            String,
            Table,
            create_engine,
        )

        from app.core.config import get_settings

        s = settings or get_settings()
        url = s.resolved_database_url
        kw: dict = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
        self._engine = create_engine(url, **kw)
        self._meta = MetaData()
        self._table = Table(
            "users",
            self._meta,
            Column("id", String, primary_key=True),
            Column("email", String, nullable=False, unique=True),
            Column("name", String, nullable=False),
            Column("hashed_password", String, nullable=False),
            Column("created_at", String, nullable=False),
            Column("updated_at", String, nullable=False),
        )
        self._meta.create_all(self._engine)
        self._lock = threading.RLock()

    def get_by_email(self, email: str) -> UserRecord | None:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(self._table.c.email == email.lower())
            ).fetchone()
        return UserRecord.from_dict(dict(row._mapping)) if row else None

    def get_by_id(self, user_id: str) -> UserRecord | None:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(self._table.c.id == user_id)
            ).fetchone()
        return UserRecord.from_dict(dict(row._mapping)) if row else None

    def create(self, email: str, name: str, hashed_password: str) -> UserRecord:
        user = UserRecord(
            id=uuid.uuid4().hex,
            email=email.lower(),
            name=name,
            hashed_password=hashed_password,
        )
        with self._lock, self._engine.begin() as conn:
            conn.execute(self._table.insert().values(**user.to_dict()))
        return user

    def update(self, user_id: str, name: str) -> UserRecord | None:
        now = _now()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                self._table.update()
                .where(self._table.c.id == user_id)
                .values(name=name, updated_at=now)
            )
        return self.get_by_id(user_id)

    def delete(self, user_id: str) -> bool:
        with self._lock, self._engine.begin() as conn:
            result = conn.execute(
                self._table.delete().where(self._table.c.id == user_id)
            )
        return result.rowcount > 0
