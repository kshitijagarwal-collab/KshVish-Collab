from __future__ import annotations

from datetime import date

import httpx
import pytest

from src.core.domain.applicant import IndividualApplicant
from src.kyc.individual.pep_screening import (
    DowJonesProvider,
    LexisNexisProvider,
    PEPCategory,
    PEPMatch,
    PEPProvider,
    StubPEPProvider,
    _get_provider,
    screen_pep,
)


def _applicant() -> IndividualApplicant:
    return IndividualApplicant(
        first_name="Alex",
        last_name="Smith",
        date_of_birth=date(1970, 3, 14),
        nationality="US",
        country_of_residence="US",
        email="alex@example.com",
    )


class _RecordingProvider:
    def __init__(self, matches: list[PEPMatch]) -> None:
        self.matches = matches
        self.calls: list[str] = []

    def query(self, applicant: IndividualApplicant) -> list[PEPMatch]:
        self.calls.append(applicant.full_name)
        return list(self.matches)


def test_stub_returns_clean() -> None:
    result = screen_pep(_applicant(), provider=StubPEPProvider())
    assert result.is_pep is False
    assert result.matches == []
    assert result.enhanced_due_diligence_required is False


def test_match_above_threshold_flags_pep() -> None:
    match = PEPMatch(
        matched_name="Alex Smith",
        category=PEPCategory.SENIOR_OFFICIAL,
        country="US",
        position="Senator",
        match_score=92.0,
        source="DOW_JONES",
    )
    rec = _RecordingProvider([match])

    result = screen_pep(_applicant(), provider=rec)

    assert result.is_pep is True
    assert result.enhanced_due_diligence_required is True
    assert result.matches == [match]


def test_match_below_threshold_does_not_flag() -> None:
    match = PEPMatch(
        matched_name="Alex Smith",
        category=PEPCategory.FAMILY_MEMBER,
        country="US",
        position="-",
        match_score=70.0,
        source="DOW_JONES",
    )
    rec = _RecordingProvider([match])

    result = screen_pep(_applicant(), provider=rec)

    assert result.is_pep is False
    assert result.enhanced_due_diligence_required is False


def test_false_positive_clearance_resets_state() -> None:
    rec = _RecordingProvider([
        PEPMatch("Alex Smith", PEPCategory.JUDICIAL, "US", "Judge", 95.0, "LEXIS_NEXIS"),
    ])
    result = screen_pep(_applicant(), provider=rec)

    result.clear_false_positive(reviewer="r1", notes="DOB mismatch")

    assert result.is_pep is False
    assert result.matches == []
    assert result.reviewed_by == "r1"


def test_factory_defaults_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KYC_PEP_PROVIDER", raising=False)
    assert isinstance(_get_provider(), StubPEPProvider)


def test_factory_selects_dow_jones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_PEP_PROVIDER", "dow_jones")
    monkeypatch.setenv("KYC_DOW_JONES_API_KEY", "dj-key")
    provider = _get_provider()
    assert isinstance(provider, DowJonesProvider)
    assert provider.api_key == "dj-key"


def test_factory_selects_lexis_nexis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_PEP_PROVIDER", "lexis_nexis")
    monkeypatch.setenv("KYC_LEXIS_NEXIS_API_KEY", "ln-key")
    provider = _get_provider()
    assert isinstance(provider, LexisNexisProvider)
    assert provider.api_key == "ln-key"


def test_dow_jones_parses_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "matches": [
                {
                    "categoryCode": "SO",
                    "name": "Alex Smith",
                    "country": "US",
                    "position": "Senator",
                    "score": 91,
                    "active": True,
                },
                {
                    "categoryCode": "UNKNOWN",
                    "name": "Other",
                    "score": 50,
                },
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = DowJonesProvider(api_key="k", client=client)

    matches = provider.query(_applicant())

    assert len(matches) == 1
    assert matches[0].category == PEPCategory.SENIOR_OFFICIAL
    assert matches[0].source == "DOW_JONES"
    assert matches[0].match_score == 91.0


def test_dow_jones_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = DowJonesProvider(api_key="k", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        provider.query(_applicant())


def test_lexis_nexis_parses_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "results": [
                {
                    "pepRole": "JUDICIAL",
                    "name": "Alex Smith",
                    "countryCode": "US",
                    "title": "Federal Judge",
                    "matchScore": 88,
                    "isActive": True,
                },
                {
                    "pepRole": "RELATIVE",
                    "name": "Family Member",
                    "countryCode": "US",
                    "title": "-",
                    "matchScore": 70,
                    "isActive": False,
                },
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = LexisNexisProvider(api_key="k", client=client)

    matches = provider.query(_applicant())

    assert {m.category for m in matches} == {PEPCategory.JUDICIAL, PEPCategory.FAMILY_MEMBER}
    assert all(m.source == "LEXIS_NEXIS" for m in matches)


def test_protocol_compliance() -> None:
    p: PEPProvider = StubPEPProvider()
    assert p.query(_applicant()) == []
