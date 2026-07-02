"""Unit tests for the Evidence Engine (RFC-0001 §3, §8)."""

import pytest

from app.evidence import base_evidence_level, downgrade, evidence_level_for_claim
from app.schemas import EvidenceLevel, Source, StudyType


def _source(study_type: StudyType) -> Source:
    return Source(study_id="s", pmid_or_doi="d", study_type=study_type, year=2020)


@pytest.mark.parametrize(
    "study_type,expected",
    [
        (StudyType.meta_analysis, EvidenceLevel.high),
        (StudyType.systematic_review, EvidenceLevel.high),
        (StudyType.rct, EvidenceLevel.moderate),
        (StudyType.cohort, EvidenceLevel.low),
        (StudyType.observational, EvidenceLevel.low),
        (StudyType.case_series, EvidenceLevel.very_low),
        (StudyType.expert_opinion, EvidenceLevel.very_low),
    ],
)
def test_base_level_per_study_type(study_type, expected):
    assert base_evidence_level([_source(study_type)]) == expected


def test_best_source_wins():
    sources = [_source(StudyType.observational), _source(StudyType.meta_analysis)]
    assert base_evidence_level(sources) == EvidenceLevel.high


def test_downgrade_stops_at_very_low():
    assert downgrade(EvidenceLevel.low, 5) == EvidenceLevel.very_low


def test_downgrade_flags_lower_level():
    sources = [_source(StudyType.meta_analysis)]
    level = evidence_level_for_claim(
        sources, small_sample=True, high_heterogeneity=True
    )
    assert level == EvidenceLevel.low  # high -> down 2 steps


def test_empty_sources_raise():
    with pytest.raises(ValueError):
        base_evidence_level([])
