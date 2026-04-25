from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from src.kyc.corporate.ubo import (
    MAX_OWNERSHIP_DEPTH,
    OpenCorporatesOwnershipProvider,
    OwnershipProvider,
    StubOwnershipProvider,
    UBO_THRESHOLD_PERCENT,
    _get_provider,
    resolve_ubos,
)


class _ScriptedProvider:
    def __init__(self, script: dict[str, list[dict]]) -> None:
        self.script = script
        self.calls: list[tuple[str, str]] = []

    def fetch(self, entity_name: str, country: str) -> list[dict]:
        self.calls.append((entity_name, country))
        return list(self.script.get(entity_name, []))


def test_individual_above_threshold_marked_ubo() -> None:
    data = [{"name": "Jane", "type": "Person", "percent": 60, "country": "GB", "is_individual": True}]
    result = resolve_ubos(uuid4(), data, provider=StubOwnershipProvider())

    assert len(result.ubos) == 1
    assert result.ubos[0].is_ubo is True
    assert result.complete is True


def test_individual_below_threshold_not_ubo() -> None:
    data = [{"name": "Jane", "type": "Person", "percent": 10, "country": "GB", "is_individual": True}]
    result = resolve_ubos(uuid4(), data, provider=StubOwnershipProvider())

    assert result.ubos == []
    assert result.complete is True


def test_corporate_owner_recurses_into_provider() -> None:
    top = [{"name": "ParentCo", "type": "Company", "percent": 80, "country": "GB", "is_individual": False}]
    provider = _ScriptedProvider({
        "ParentCo": [
            {"name": "Owner Person", "type": "Person", "percent": 100, "country": "GB", "is_individual": True},
        ]
    })

    result = resolve_ubos(uuid4(), top, provider=provider)

    assert provider.calls == [("ParentCo", "GB")]
    assert len(result.ubos) == 1
    assert result.ubos[0].entity_name == "Owner Person"
    assert result.complete is True


def test_corporate_owner_below_threshold_not_recursed() -> None:
    top = [{"name": "ParentCo", "type": "Company", "percent": 10, "country": "GB", "is_individual": False}]
    provider = _ScriptedProvider({})

    result = resolve_ubos(uuid4(), top, provider=provider)

    assert provider.calls == []
    assert result.ubos == []


def test_unresolved_corporate_owner_marks_layer() -> None:
    top = [{"name": "OpaqueCo", "type": "Company", "percent": 50, "country": "KY", "is_individual": False}]
    provider = _ScriptedProvider({})

    result = resolve_ubos(uuid4(), top, provider=provider)

    assert "OpaqueCo" in result.unresolved_layers
    assert result.complete is False


def test_max_depth_reached_terminates_recursion() -> None:
    chain = {f"Layer{i}": [{
        "name": f"Layer{i+1}",
        "type": "Company",
        "percent": 100,
        "country": "GB",
        "is_individual": False,
    }] for i in range(MAX_OWNERSHIP_DEPTH + 5)}
    provider = _ScriptedProvider(chain)

    top = [{"name": "Layer0", "type": "Company", "percent": 100, "country": "GB", "is_individual": False}]
    result = resolve_ubos(uuid4(), top, provider=provider)

    assert result.max_depth_reached is True
    assert result.complete is False


def test_threshold_constant_is_25_percent() -> None:
    assert UBO_THRESHOLD_PERCENT == 25.0


def test_factory_defaults_to_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KYC_OWNERSHIP_PROVIDER", raising=False)
    assert isinstance(_get_provider(), StubOwnershipProvider)


def test_factory_selects_open_corporates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYC_OWNERSHIP_PROVIDER", "open_corporates")
    monkeypatch.setenv("KYC_OPEN_CORPORATES_API_KEY", "oc-key")
    provider = _get_provider()
    assert isinstance(provider, OpenCorporatesOwnershipProvider)
    assert provider.api_key == "oc-key"


def test_open_corporates_returns_empty_when_company_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"companies": []}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenCorporatesOwnershipProvider(client=client)

    assert provider.fetch("UnknownCo", "GB") == []


def test_open_corporates_parses_beneficial_ownership() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={
                "results": {
                    "companies": [{
                        "company": {
                            "company_number": "12345678",
                            "jurisdiction_code": "gb",
                        }
                    }]
                }
            })
        return httpx.Response(200, json={
            "results": {
                "statements": [
                    {"statement": {
                        "statement_type": "beneficial_ownership",
                        "percentage_of_shares": 60,
                        "interested_party": {
                            "name": "Jane Doe",
                            "entity_type": "Person",
                            "country": "GB",
                        },
                    }},
                    {"statement": {
                        "statement_type": "control_via_resolution",
                        "interested_party": {"name": "Other"},
                    }},
                ]
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenCorporatesOwnershipProvider(client=client)

    data = provider.fetch("Acme", "GB")

    assert len(data) == 1
    assert data[0]["name"] == "Jane Doe"
    assert data[0]["is_individual"] is True
    assert data[0]["percent"] == 60.0


def test_open_corporates_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenCorporatesOwnershipProvider(client=client)

    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch("Acme", "GB")


def test_protocol_compliance() -> None:
    p: OwnershipProvider = StubOwnershipProvider()
    assert p.fetch("X", "GB") == []
