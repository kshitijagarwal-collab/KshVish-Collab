from __future__ import annotations
import pytest
from uuid import uuid4

from src.kyc.corporate.ubo import (
    MAX_OWNERSHIP_DEPTH,
    UBO_THRESHOLD_PERCENT,
    resolve_ubos,
)


def _individual_owner(name: str, percent: float, country: str = "GB") -> dict:
    return {"name": name, "type": "INDIVIDUAL", "percent": percent, "country": country, "is_individual": True}


def _corporate_owner(name: str, percent: float, country: str = "GB") -> dict:
    return {"name": name, "type": "COMPANY", "percent": percent, "country": country, "is_individual": False}


class TestResolveUBOs:
    def test_individual_above_threshold_is_ubo(self):
        data = [_individual_owner("Alice Smith", 60.0)]
        result = resolve_ubos(uuid4(), data)
        assert len(result.ubos) == 1
        assert result.ubos[0].entity_name == "Alice Smith"

    def test_individual_below_threshold_is_not_ubo(self):
        data = [_individual_owner("Bob Jones", 10.0)]
        result = resolve_ubos(uuid4(), data)
        assert len(result.ubos) == 0

    def test_individual_at_exact_threshold_is_ubo(self):
        data = [_individual_owner("Carol White", UBO_THRESHOLD_PERCENT)]
        result = resolve_ubos(uuid4(), data)
        assert len(result.ubos) == 1

    def test_multiple_ubos_all_captured(self):
        data = [
            _individual_owner("Alice Smith", 40.0),
            _individual_owner("Bob Jones", 35.0),
        ]
        result = resolve_ubos(uuid4(), data)
        assert len(result.ubos) == 2

    def test_no_owners_returns_complete_empty(self):
        result = resolve_ubos(uuid4(), [])
        assert result.ubos == []
        assert result.complete

    def test_corporate_owner_above_threshold_with_no_registry_data_is_unresolved(self):
        # _fetch_ownership_data stub returns [] for corporate owners
        data = [_corporate_owner("Shell Corp Ltd", 80.0)]
        result = resolve_ubos(uuid4(), data)
        assert "Shell Corp Ltd" in result.unresolved_layers
        assert not result.complete

    def test_max_depth_returns_incomplete(self):
        data = [_individual_owner("Alice Smith", 60.0)]
        result = resolve_ubos(uuid4(), data, depth=MAX_OWNERSHIP_DEPTH)
        assert result.max_depth_reached
        assert result.ubos == []
        assert not result.complete

    def test_effective_ownership_verified_requires_no_unresolved(self):
        data = [_individual_owner("Alice Smith", 60.0)]
        result = resolve_ubos(uuid4(), data)
        assert result.effective_ownership_verified()

    def test_effective_ownership_not_verified_with_unresolved_layers(self):
        data = [_corporate_owner("Opaque Corp", 80.0)]
        result = resolve_ubos(uuid4(), data)
        assert not result.effective_ownership_verified()

    def test_ownership_tree_includes_all_parsed_nodes(self):
        data = [
            _individual_owner("Alice Smith", 60.0),
            _individual_owner("Bob Jones", 40.0),
        ]
        result = resolve_ubos(uuid4(), data)
        assert len(result.ownership_tree) == 2
