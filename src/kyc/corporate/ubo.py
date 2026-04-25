from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4


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


def resolve_ubos(
    corporate_id: UUID,
    ownership_data: list[dict],
    depth: int = 0,
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
            # Recurse into corporate owner
            sub_data = _fetch_ownership_data(node.entity_name, node.country)
            if sub_data:
                sub_result = resolve_ubos(node.id, sub_data, depth + 1)
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
    # Integration point: company registry APIs, OpenCorporates, etc.
    return []
