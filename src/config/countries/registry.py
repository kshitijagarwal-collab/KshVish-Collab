from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache

from src.core.domain.document import DocumentType


@dataclass
class CountryRules:
    country_code: str
    country_name: str
    fatf_status: str
    required_identity_doc_types: set[DocumentType]
    required_address_doc_types: set[DocumentType]
    enhanced_due_diligence: bool = False
    rekyc_months: int = 24
    min_address_doc_age_months: int = 3
    ubo_threshold_override: float | None = None
    notes: str = ""


_DEFAULT_RULES = CountryRules(
    country_code="DEFAULT",
    country_name="Default",
    fatf_status="STANDARD",
    required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID},
    required_address_doc_types={DocumentType.PROOF_OF_ADDRESS},
    rekyc_months=24,
)

_COUNTRY_REGISTRY: dict[str, CountryRules] = {
    "GB": CountryRules(
        country_code="GB",
        country_name="United Kingdom",
        fatf_status="STANDARD",
        required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID, DocumentType.DRIVING_LICENCE},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS, DocumentType.UTILITY_BILL},
        rekyc_months=24,
    ),
    "US": CountryRules(
        country_code="US",
        country_name="United States",
        fatf_status="STANDARD",
        required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS},
        rekyc_months=12,
        notes="FinCEN CDD Rule applies for fund investments",
    ),
    "IN": CountryRules(
        country_code="IN",
        country_name="India",
        fatf_status="STANDARD",
        required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS},
        rekyc_months=24,
        notes="PAN card required for investments above INR 50,000",
    ),
    "AE": CountryRules(
        country_code="AE",
        country_name="United Arab Emirates",
        fatf_status="ENHANCED",
        required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS},
        enhanced_due_diligence=True,
        rekyc_months=12,
    ),
    "SG": CountryRules(
        country_code="SG",
        country_name="Singapore",
        fatf_status="STANDARD",
        required_identity_doc_types={DocumentType.PASSPORT, DocumentType.NATIONAL_ID},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS},
        rekyc_months=24,
    ),
    "KY": CountryRules(
        country_code="KY",
        country_name="Cayman Islands",
        fatf_status="STANDARD",
        required_identity_doc_types={DocumentType.PASSPORT},
        required_address_doc_types={DocumentType.PROOF_OF_ADDRESS, DocumentType.BANK_STATEMENT},
        rekyc_months=12,
        notes="CIMA regulated funds require enhanced documentation",
    ),
}


@lru_cache(maxsize=300)
def get_country_rules(country_code: str) -> CountryRules:
    return _COUNTRY_REGISTRY.get(country_code.upper(), _DEFAULT_RULES)


def register_country(rules: CountryRules) -> None:
    _COUNTRY_REGISTRY[rules.country_code] = rules
    get_country_rules.cache_clear()


def list_high_risk_countries() -> list[str]:
    return [c for c, r in _COUNTRY_REGISTRY.items() if r.fatf_status in ("HIGH_RISK", "ENHANCED")]
