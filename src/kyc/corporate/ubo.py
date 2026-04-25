from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID, uuid4

import httpx


UBO_THRESHOLD_PERCENT = 25.0
MAX_OWNERSHIP_DEPTH = 10


@dataclass
class OwnershipNode:
    entity_name: str
    entity_type: str
    ownership_percent: float
    country: str
    id: UUID = field(default_factory=uuid4)
    parent_id: Optional[UUID] = None
    is_individual: bool = False
    is_ubo: bool = False
    kyc_case_id: Optional[UUID] = None


@dataclass
class UBOResolutionResult:
    corporate_id: UUID
    ubos: list[OwnershipNode] = field(default_factory=list)
    ownership_tree: list[OwnershipNode] = field(default_factory=list)
    complete: bool = False
    max_depth_reached: bool = False
    unresolved_layers: list[str] = field(default_factory=list)

    def add_ubo(self, node: OwnershipNode) -> None:
        node.is_ubo = True
        self.ubos.append(node)

    def effective_ownership_verified(self) -> bool:
        return self.complete and len(self.unresolved_layers) == 0


class OwnershipProvider(Protocol):
    def fetch(self, entity_name: str, country: str) -> list[dict]: ...


class StubOwnershipProvider:
    def fetch(self, entity_name: str, country: str) -> list[dict]:
        return []


@dataclass
class OpenCorporatesOwnershipProvider:
    api_key: Optional[str] = None
    base_url: str = "https://api.opencorporates.com/v0.4"
    timeout: float = 10.0
    client: Optional[httpx.Client] = None

    def fetch(self, entity_name: str, country: str) -> list[dict]:
        client = self.client or httpx.Client(timeout=self.timeout)
        try:
            params = {"q": entity_name, "jurisdiction_code": country.lower()}
            if self.api_key:
                params["api_token"] = self.api_key

            companies_resp = client.get(f"{self.base_url}/companies/search", params=params)
            companies_resp.raise_for_status()
            company = _first_company(companies_resp.json())
            if company is None:
                return []

            jurisdiction = company.get("jurisdiction_code", country.lower())
            company_number = company.get("company_number")
            if not company_number:
                return []

            stmt_params = {"api_token": self.api_key} if self.api_key else {}
            stmts_resp = client.get(
                f"{self.base_url}/companies/{jurisdiction}/{company_number}/statements",
                params=stmt_params,
            )
            stmts_resp.raise_for_status()
            return _parse_ownership_statements(stmts_resp.json())
        finally:
            if self.client is None:
                client.close()


def _first_company(body: dict) -> Optional[dict]:
    companies = body.get("results", {}).get("companies", [])
    if not companies:
        return None
    return companies[0].get("company")


def _parse_ownership_statements(body: dict) -> list[dict]:
    statements = body.get("results", {}).get("statements", [])
    out: list[dict] = []
    for wrapper in statements:
        stmt = wrapper.get("statement", {})
        if stmt.get("statement_type") != "beneficial_ownership":
            continue
        interested_party = stmt.get("interested_party", {})
        is_individual = interested_party.get("entity_type") == "Person"
        out.append({
            "name": interested_party.get("name", ""),
            "type": interested_party.get("entity_type", "UNKNOWN"),
            "percent": float(stmt.get("percentage_of_shares", 0)),
            "country": interested_party.get("country", "XX"),
            "is_individual": is_individual,
        })
    return out


def resolve_ubos(
    corporate_id: UUID,
    ownership_data: list[dict],
    depth: int = 0,
    provider: OwnershipProvider | None = None,
) -> UBOResolutionResult:
    selected = provider or _get_provider()
    return _resolve(corporate_id, ownership_data, depth, selected)


def _resolve(
    corporate_id: UUID,
    ownership_data: list[dict],
    depth: int,
    provider: OwnershipProvider,
) -> UBOResolutionResult:
    result = UBOResolutionResult(corporate_id=corporate_id)

    if depth >= MAX_OWNERSHIP_DEPTH:
        result.max_depth_reached = True
        return result

    nodes = _parse_ownership_data(ownership_data, corporate_id)
    result.ownership_tree.extend(nodes)

    for node in nodes:
        if node.is_individual and node.ownership_percent >= UBO_THRESHOLD_PERCENT:
            result.add_ubo(node)
        elif not node.is_individual and node.ownership_percent >= UBO_THRESHOLD_PERCENT:
            sub_data = provider.fetch(node.entity_name, node.country)
            if sub_data:
                sub_result = _resolve(node.id, sub_data, depth + 1, provider)
                result.ubos.extend(sub_result.ubos)
                result.ownership_tree.extend(sub_result.ownership_tree)
                if sub_result.max_depth_reached:
                    result.max_depth_reached = True
            else:
                result.unresolved_layers.append(node.entity_name)

    result.complete = not result.max_depth_reached and len(result.unresolved_layers) == 0
    return result


def _parse_ownership_data(data: list[dict], parent_id: UUID) -> list[OwnershipNode]:
    nodes = []
    for item in data:
        nodes.append(OwnershipNode(
            entity_name=item["name"],
            entity_type=item.get("type", "UNKNOWN"),
            ownership_percent=float(item.get("percent", 0)),
            country=item.get("country", "XX"),
            parent_id=parent_id,
            is_individual=item.get("is_individual", False),
        ))
    return nodes


def _fetch_ownership_data(entity_name: str, country: str) -> list[dict]:
    return _get_provider().fetch(entity_name, country)


def _get_provider() -> OwnershipProvider:
    name = os.getenv("KYC_OWNERSHIP_PROVIDER", "stub").lower()
    if name == "open_corporates":
        return OpenCorporatesOwnershipProvider(
            api_key=os.environ.get("KYC_OPEN_CORPORATES_API_KEY"),
        )
    return StubOwnershipProvider()
