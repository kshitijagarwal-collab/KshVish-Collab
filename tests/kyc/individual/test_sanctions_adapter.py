from __future__ import annotations

from datetime import date

import httpx
import pytest

from src.core.domain.applicant import IndividualApplicant
from src.kyc.individual.sanctions import (
    ComplyAdvantageProvider,
    RefinitivProvider,
    SanctionsHit,
    SanctionsList,
    SanctionsProvider,
    StubSanctionsProvider,
    _get_provider,
    screen_individual,
)


def _applicant() -> IndividualApplicant:
    return IndividualApplicant(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1985, 6, 1),
        nationality="GB",
        country_of_residence="GB",
        email="jane@example.com",
    )


class _RecordingProvider:
    def __init__(self, hits: list[SanctionsHit]) -> None:
        self.hits = hits
        self.calls: list[tuple] = []

    def screen(
        self,
        applicant: IndividualApplicant,
        lists: list[SanctionsList],
    ) -> list[SanctionsHit]:
        self.calls.append((applicant.id, tuple(lists)))
        return list(self.hits)


def test_stub_returns_clean() -> None:
    result = screen_individual(_applicant(), provider=StubSanctionsProvider())
    assert result.is_clear is True
    assert result.hits == []
    assert set(result.lists_checked) == set(SanctionsList)


def test_provider_hit_marks_unclear() -> None:
    hit = SanctionsHit(
        list_name=SanctionsList.OFAC_SDN,
        matched_name="Jane Doe",
        match_score=92.0,
        reference="OFAC-12345",
        details="Listed entity",
    )
    rec = _RecordingProvider([hit])

    result = screen_individual(_applicant(), provider=rec)

    assert result.is_clear is False
    assert result.has_confirmed_hit() is True
    assert result.hits == [hit]


def test_false_positive_clearance() -> None:
    rec = _RecordingProvider([
        SanctionsHit(SanctionsList.UN_CONSOLIDATED, "Jane Doe", 88.0, "UN-1", ""),
    ])
    result = screen_individual(_applicant(), provider=rec)

    result.clear_as_false_positive(actor="reviewer-1", reason="DOB mismatch")

    assert result.has_confirmed_hit() is False
    assert result.cleared_by == "reviewer-1"
    assert result.cleared_reason == "DOB mismatch"


def test_lists_filter_passed_to_provider() -> None:
    rec = _RecordingProvider([])
    screen_individual(
        _applicant(),
        lists=[SanctionsList.OFAC_SDN, SanctionsList.UK_HMT],
        provider=rec,
    )
    assert rec.calls[0][1] == (SanctionsList.OFAC_SDN, SanctionsList.UK_HMT)


def test_factory_defaults_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KYC_SANCTIONS_PROVIDER", raising=False)
    assert isinstance(_get_provider(), StubSanctionsProvider)


def test_factory_selects_comply_advantage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_SANCTIONS_PROVIDER", "comply_advantage")
    monkeypatch.setenv("KYC_COMPLY_ADVANTAGE_API_KEY", "test-key")
    provider = _get_provider()
    assert isinstance(provider, ComplyAdvantageProvider)
    assert provider.api_key == "test-key"


def test_factory_selects_refinitiv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_SANCTIONS_PROVIDER", "refinitiv")
    monkeypatch.setenv("KYC_REFINITIV_API_KEY", "rk")
    monkeypatch.setenv("KYC_REFINITIV_GROUP_ID", "grp-1")
    provider = _get_provider()
    assert isinstance(provider, RefinitivProvider)
    assert provider.api_key == "rk"
    assert provider.group_id == "grp-1"


def test_comply_advantage_parses_hit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": {
                "hits": [
                    {
                        "list_code": "ofac-sdn",
                        "name": "Jane Doe",
                        "score": 95,
                        "reference": "SDN-1",
                        "notes": "match",
                    },
                    {
                        "list_code": "ofac-sdn",
                        "name": "Other",
                        "score": 60,
                        "reference": "SDN-2",
                        "notes": "weak",
                    },
                ]
            }
        })

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = ComplyAdvantageProvider(api_key="k", client=client)

    hits = provider.screen(_applicant(), [SanctionsList.OFAC_SDN])

    assert len(hits) == 2
    assert hits[0].list_name == SanctionsList.OFAC_SDN
    assert hits[0].match_score == 95.0
    assert hits[0].reference == "SDN-1"


def test_comply_advantage_filters_unrequested_lists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": {
                "hits": [
                    {"list_code": "ofac-sdn", "name": "X", "score": 90, "reference": "1"},
                    {"list_code": "uk-hmt", "name": "Y", "score": 90, "reference": "2"},
                ]
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ComplyAdvantageProvider(api_key="k", client=client)

    hits = provider.screen(_applicant(), [SanctionsList.OFAC_SDN])

    assert [h.list_name for h in hits] == [SanctionsList.OFAC_SDN]


def test_comply_advantage_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ComplyAdvantageProvider(api_key="k", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        provider.screen(_applicant(), [SanctionsList.OFAC_SDN])


def test_refinitiv_parses_hit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "results": [{
                "matchedTerm": "Jane Doe",
                "matchStrength": 87,
                "referenceId": "WC-1",
                "sources": [
                    {"type": "OFAC", "description": "OFAC listed"},
                    {"type": "UN", "description": "UN listed"},
                ],
            }]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RefinitivProvider(api_key="k", group_id="g", client=client)

    hits = provider.screen(_applicant(), [SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED])

    assert {h.list_name for h in hits} == {SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED}
    assert hits[0].match_score == 87.0


def test_protocol_compliance() -> None:
    p: SanctionsProvider = StubSanctionsProvider()
    assert p.screen(_applicant(), [SanctionsList.OFAC_SDN]) == []
