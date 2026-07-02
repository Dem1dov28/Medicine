"""Repository: the only place that maps between the Pydantic Claim and storage.

Keeping serialisation in one place means the rest of the app works purely with
the typed ``Claim`` model (RFC-0001 §2), never raw rows.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas import Claim, ClaimStatus
from app.storage.models import ClaimRecord


def _to_record(claim: Claim, source_text: str | None = None) -> ClaimRecord:
    return ClaimRecord(
        id=str(claim.id),
        subject=claim.subject.strip().lower(),
        outcome=claim.outcome.strip().lower(),
        status=claim.status.value,
        document=claim.model_dump(mode="json"),
        source_text=source_text,
    )


def _to_claim(record: ClaimRecord) -> Claim:
    return Claim.model_validate(record.document)


class ClaimRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, claim: Claim, source_text: str | None = None) -> Claim:
        self.session.add(_to_record(claim, source_text))
        self.session.commit()
        return claim

    def get(self, claim_id: UUID) -> Claim | None:
        record = self.session.get(ClaimRecord, str(claim_id))
        return _to_claim(record) if record else None

    def get_source_text(self, claim_id: UUID) -> str | None:
        record = self.session.get(ClaimRecord, str(claim_id))
        return record.source_text if record else None

    def update(self, claim: Claim) -> Claim:
        record = self.session.get(ClaimRecord, str(claim.id))
        if record is None:
            raise KeyError(claim.id)
        record.subject = claim.subject.strip().lower()
        record.outcome = claim.outcome.strip().lower()
        record.status = claim.status.value
        record.document = claim.model_dump(mode="json")
        self.session.commit()
        return claim

    def list_by_subject(
        self, subject: str, *, status: ClaimStatus | None = None
    ) -> list[Claim]:
        stmt = select(ClaimRecord).where(
            ClaimRecord.subject == subject.strip().lower()
        )
        if status is not None:
            stmt = stmt.where(ClaimRecord.status == status.value)
        return [_to_claim(r) for r in self.session.scalars(stmt)]

    def list_published(self) -> list[Claim]:
        stmt = select(ClaimRecord).where(
            ClaimRecord.status == ClaimStatus.published.value
        )
        return [_to_claim(r) for r in self.session.scalars(stmt)]

    def search(self, terms: list[str]) -> list[Claim]:
        """Naive keyword match over subject/outcome for /ask in v0."""
        stmt = select(ClaimRecord).where(
            ClaimRecord.status == ClaimStatus.published.value
        )
        results: list[Claim] = []
        for record in self.session.scalars(stmt):
            haystack = f"{record.subject} {record.outcome}"
            if any(term.lower() in haystack for term in terms):
                results.append(_to_claim(record))
        return results
