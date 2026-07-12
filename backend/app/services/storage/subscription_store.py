"""Subscription persistence — tracks Stripe plan status per user."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import Column, MetaData, String, Table, create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SubscriptionRecord:
    user_id: str
    stripe_customer_id: str
    stripe_subscription_id: str = ""
    status: str = "inactive"       # active | canceled | past_due | inactive
    current_period_end: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def is_pro(self) -> bool:
        return self.status == "active"


class SubscriptionStore:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or get_settings()
        url = resolved.resolved_database_url
        resolved.storage_dir.mkdir(parents=True, exist_ok=True)

        engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        self._engine = create_engine(url, **engine_kwargs)
        self._meta = MetaData()
        self._table = Table(
            "subscriptions",
            self._meta,
            Column("user_id", String(128), primary_key=True),
            Column("stripe_customer_id", String(128), nullable=False),
            Column("stripe_subscription_id", String(128), nullable=False, default=""),
            Column("status", String(32), nullable=False, default="inactive"),
            Column("current_period_end", String(64), nullable=False, default=""),
            Column("created_at", String(64), nullable=False),
            Column("updated_at", String(64), nullable=False),
        )
        self._meta.create_all(self._engine)

    def _to_record(self, row) -> SubscriptionRecord:
        m = row._mapping
        return SubscriptionRecord(
            user_id=m["user_id"],
            stripe_customer_id=m["stripe_customer_id"],
            stripe_subscription_id=m["stripe_subscription_id"],
            status=m["status"],
            current_period_end=m["current_period_end"],
            created_at=m["created_at"],
            updated_at=m["updated_at"],
        )

    def get(self, user_id: str) -> SubscriptionRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(self._table.c.user_id == user_id)
            ).first()
        return self._to_record(row) if row else None

    def get_by_customer(self, stripe_customer_id: str) -> SubscriptionRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(self._table).where(
                    self._table.c.stripe_customer_id == stripe_customer_id
                )
            ).first()
        return self._to_record(row) if row else None

    def upsert(self, record: SubscriptionRecord) -> None:
        record.updated_at = _now()
        values = {
            "user_id": record.user_id,
            "stripe_customer_id": record.stripe_customer_id,
            "stripe_subscription_id": record.stripe_subscription_id,
            "status": record.status,
            "current_period_end": record.current_period_end,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        with self._engine.begin() as conn:
            if self._engine.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                stmt = sqlite_insert(self._table).values(**values)
                update_cols = {c: stmt.excluded[c] for c in values if c != "user_id"}
                stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=update_cols)
                conn.execute(stmt)
            else:
                conn.execute(delete(self._table).where(self._table.c.user_id == record.user_id))
                conn.execute(self._table.insert().values(**values))

    def delete(self, user_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(self._table).where(self._table.c.user_id == user_id))


@lru_cache(maxsize=1)
def get_subscription_store() -> SubscriptionStore:
    return SubscriptionStore(get_settings())
