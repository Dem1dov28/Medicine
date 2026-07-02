"""SQLAlchemy models.

The full Claim lives in a JSON ``document`` column (RFC-0001 §1: "Claim as a
JSONB document"). A few scalar columns are duplicated out of the document purely
so we can index and filter cheaply (subject / outcome / status).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimRecord(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Denormalised, indexed query keys.
    subject: Mapped[str] = mapped_column(String, index=True)
    outcome: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)

    # Source of truth: the serialised Claim (Pydantic model_dump).
    document: Mapped[dict] = mapped_column(JSON)

    # Raw article text kept for verification + provenance (RFC-0002).
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
