from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from src.core.domain.document import DocumentType


_VALID_FATF_STATUSES = {"STANDARD", "ENHANCED", "HIGH_RISK"}
_DEFAULT_FILE_NAME = "_default.yaml"
_RULES_DIR = Path(__file__).parent / "rules"


class CountryRulesSchemaError(ValueError):
    pass


@dataclass
class CountryRules:
    country_code: str
    country_name: str
    fatf_status: str
    required_identity_doc_types: set[DocumentType] = field(default_factory=set)
    required_address_doc_types: set[DocumentType] = field(default_factory=set)
    enhanced_due_diligence: bool = False
    rekyc_months: int = 24
    min_address_doc_age_months: int = 3
    ubo_threshold_override: Optional[float] = None
    notes: str = ""


def _parse_doc_types(value: Any, *, field_name: str, country_code: str) -> set[DocumentType]:
    if value is None:
        return set()
    if not isinstance(value, list):
        raise CountryRulesSchemaError(
            f"{country_code}: '{field_name}' must be a list of DocumentType names"
        )
    out: set[DocumentType] = set()
    for raw in value:
        if not isinstance(raw, str):
            raise CountryRulesSchemaError(
                f"{country_code}: '{field_name}' entries must be strings"
            )
        try:
            out.add(DocumentType(raw))
        except ValueError as exc:
            raise CountryRulesSchemaError(
                f"{country_code}: unknown DocumentType '{raw}' in '{field_name}'"
            ) from exc
    return out


def _parse_rules(data: dict, *, source: str) -> CountryRules:
    if not isinstance(data, dict):
        raise CountryRulesSchemaError(f"{source}: top-level must be a mapping")

    code = data.get("country_code")
    if not isinstance(code, str) or not code:
        raise CountryRulesSchemaError(f"{source}: 'country_code' is required and must be a string")

    name = data.get("country_name")
    if not isinstance(name, str) or not name:
        raise CountryRulesSchemaError(f"{code}: 'country_name' is required")

    fatf = data.get("fatf_status")
    if fatf not in _VALID_FATF_STATUSES:
        raise CountryRulesSchemaError(
            f"{code}: 'fatf_status' must be one of {sorted(_VALID_FATF_STATUSES)}"
        )

    ubo_override = data.get("ubo_threshold_override")
    if ubo_override is not None and not isinstance(ubo_override, (int, float)):
        raise CountryRulesSchemaError(
            f"{code}: 'ubo_threshold_override' must be a number or null"
        )

    return CountryRules(
        country_code=code.upper(),
        country_name=name,
        fatf_status=fatf,
        required_identity_doc_types=_parse_doc_types(
            data.get("required_identity_doc_types"),
            field_name="required_identity_doc_types",
            country_code=code,
        ),
        required_address_doc_types=_parse_doc_types(
            data.get("required_address_doc_types"),
            field_name="required_address_doc_types",
            country_code=code,
        ),
        enhanced_due_diligence=bool(data.get("enhanced_due_diligence", False)),
        rekyc_months=int(data.get("rekyc_months", 24)),
        min_address_doc_age_months=int(data.get("min_address_doc_age_months", 3)),
        ubo_threshold_override=float(ubo_override) if ubo_override is not None else None,
        notes=str(data.get("notes", "")),
    )


def load_rules_from_dir(rules_dir: Path) -> tuple[CountryRules, dict[str, CountryRules]]:
    if not rules_dir.is_dir():
        raise CountryRulesSchemaError(f"Rules directory not found: {rules_dir}")

    default_path = rules_dir / _DEFAULT_FILE_NAME
    if not default_path.is_file():
        raise CountryRulesSchemaError(f"Default rules file not found: {default_path}")

    default = _parse_rules(yaml.safe_load(default_path.read_text(encoding="utf-8")), source=_DEFAULT_FILE_NAME)

    registry: dict[str, CountryRules] = {}
    for path in sorted(rules_dir.glob("*.yaml")):
        if path.name == _DEFAULT_FILE_NAME:
            continue
        rules = _parse_rules(yaml.safe_load(path.read_text(encoding="utf-8")), source=path.name)
        registry[rules.country_code] = rules

    return default, registry


_DEFAULT_RULES, _COUNTRY_REGISTRY = load_rules_from_dir(_RULES_DIR)


@lru_cache(maxsize=300)
def get_country_rules(country_code: str) -> CountryRules:
    return _COUNTRY_REGISTRY.get(country_code.upper(), _DEFAULT_RULES)


def register_country(rules: CountryRules) -> None:
    _COUNTRY_REGISTRY[rules.country_code] = rules
    get_country_rules.cache_clear()


def list_high_risk_countries() -> list[str]:
    return [c for c, r in _COUNTRY_REGISTRY.items() if r.fatf_status in ("HIGH_RISK", "ENHANCED")]


def all_country_codes() -> list[str]:
    return sorted(_COUNTRY_REGISTRY.keys())


def reload_rules() -> None:
    global _DEFAULT_RULES, _COUNTRY_REGISTRY
    _DEFAULT_RULES, _COUNTRY_REGISTRY = load_rules_from_dir(_RULES_DIR)
    get_country_rules.cache_clear()
