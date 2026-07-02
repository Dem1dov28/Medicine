"""API contract for v0 (RFC-0001 §4).

Every endpoint returns Pydantic models, so the OpenAPI schema is the contract.
No endpoint returns bare text without linked Claims/sources.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.extraction import extract_claim
from app.reasoning import answer_question
from app.consensus import summarise_subject
from app.schemas import (
    Answer,
    Claim,
    ClaimStatus,
    ExtractRequest,
    SubstanceSummary,
)
from app.services import build_draft_claim, parse_uuid, verify_claim_llm
from app.storage import get_session
from app.storage.repository import ClaimRepository

router = APIRouter()


def _repo(session: Session = Depends(get_session)) -> ClaimRepository:
    return ClaimRepository(session)


@router.post("/internal/extract", response_model=Claim, status_code=201, tags=["internal"])
def extract(req: ExtractRequest, repo: ClaimRepository = Depends(_repo)) -> Claim:
    """Run text through extraction, store the result as a draft Claim.

    The raw source text is persisted alongside the draft so the verification
    ensemble can ground each field against it (RFC-0002).
    """
    data = extract_claim(req.text, subject=req.subject)
    claim = build_draft_claim(data)
    return repo.add(claim, source_text=req.text)


@router.get("/claims", response_model=list[Claim], tags=["claims"])
def list_claims(
    subject: str = Query(..., description="Substance name"),
    status: ClaimStatus | None = Query(None),
    repo: ClaimRepository = Depends(_repo),
) -> list[Claim]:
    return repo.list_by_subject(subject, status=status)


@router.get("/claims/{claim_id}", response_model=Claim, tags=["claims"])
def get_claim(claim_id: str, repo: ClaimRepository = Depends(_repo)) -> Claim:
    uid = parse_uuid(claim_id)
    claim = repo.get(uid) if uid else None
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/claims/{claim_id}/verify", response_model=Claim, tags=["claims"])
def verify(claim_id: str, repo: ClaimRepository = Depends(_repo)) -> Claim:
    """Run autonomous LLM-ensemble verification (RFC-0002).

    No human input: the ensemble decides published / held / rejected and the
    decision provenance is attached to the Claim.
    """
    uid = parse_uuid(claim_id)
    claim = repo.get(uid) if uid else None
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    source_text = repo.get_source_text(uid) or ""
    if not source_text:
        raise HTTPException(
            status_code=409,
            detail="No source text stored for this Claim; cannot verify.",
        )

    updated = verify_claim_llm(claim, source_text)
    return repo.update(updated)


@router.get(
    "/substances/{name}/summary",
    response_model=SubstanceSummary,
    tags=["consensus"],
)
def substance_summary(name: str, repo: ClaimRepository = Depends(_repo)) -> SubstanceSummary:
    published = repo.list_by_subject(name, status=ClaimStatus.published)
    return summarise_subject(name, published)


@router.get("/ask", response_model=Answer, tags=["reasoning"])
def ask(
    q: str = Query(..., description="A question about a substance"),
    repo: ClaimRepository = Depends(_repo),
) -> Answer:
    return answer_question(q, repo)
