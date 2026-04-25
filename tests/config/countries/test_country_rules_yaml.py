from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.countries.registry import (
    CountryRulesSchemaError,
    _parse_rules,
    all_country_codes,
    get_country_rules,
    list_high_risk_countries,
    load_rules_from_dir,
)
from src.core.domain.document import DocumentType


REQUIRED_COUNTRIES = {"GB", "US", "IN", "AE", "SG", "KY", "DE", "FR", "CH", "HK", "LU"}


def test_all_required_countries_loaded() -> None:
    assert REQUIRED_COUNTRIES.issubset(set(all_country_codes()))


def test_no_extra_countries_beyond_required() -> None:
    assert set(all_country_codes()) == REQUIRED_COUNTRIES


def test_unknown_country_falls_back_to_default() -> None:
    rules = get_country_rules("ZZ")
    assert rules.country_code == "DEFAULT"
    assert rules.fatf_status == "STANDARD"


def test_country_code_lookup_is_case_insensitive() -> None:
    assert get_country_rules("gb").country_code == "GB"
    assert get_country_rules("Gb").country_code == "GB"


def test_ae_is_enhanced_dd() -> None:
    ae = get_country_rules("AE")
    assert ae.fatf_status == "ENHANCED"
    assert ae.enhanced_due_diligence is True
    assert ae.rekyc_months == 12


def test_high_risk_listing_includes_enhanced_jurisdictions() -> None:
    high_risk = list_high_risk_countries()
    assert "AE" in high_risk


def test_doc_types_parsed_into_enum() -> None:
    gb = get_country_rules("GB")
    assert DocumentType.PASSPORT in gb.required_identity_doc_types
    assert DocumentType.DRIVING_LICENCE in gb.required_identity_doc_types
    assert DocumentType.UTILITY_BILL in gb.required_address_doc_types


def test_us_rekyc_overrides_default() -> None:
    assert get_country_rules("US").rekyc_months == 12


def test_ky_requires_passport_only_for_id() -> None:
    ky = get_country_rules("KY")
    assert ky.required_identity_doc_types == {DocumentType.PASSPORT}
    assert DocumentType.BANK_STATEMENT in ky.required_address_doc_types


def test_lu_notes_capture_fund_domicile_context() -> None:
    lu = get_country_rules("LU")
    assert "CSSF" in lu.notes
    assert "UCITS" in lu.notes


def test_invalid_fatf_status_raises(tmp_path: Path) -> None:
    (tmp_path / "_default.yaml").write_text(_minimal_yaml("DEFAULT", "STANDARD"))
    (tmp_path / "xx.yaml").write_text(_minimal_yaml("XX", "BOGUS"))

    with pytest.raises(CountryRulesSchemaError, match="fatf_status"):
        load_rules_from_dir(tmp_path)


def test_unknown_doc_type_raises(tmp_path: Path) -> None:
    (tmp_path / "_default.yaml").write_text(_minimal_yaml("DEFAULT", "STANDARD"))
    (tmp_path / "xx.yaml").write_text(
        "country_code: XX\n"
        "country_name: Test\n"
        "fatf_status: STANDARD\n"
        "required_identity_doc_types:\n"
        "  - PASSPORT_DELUXE\n"
    )

    with pytest.raises(CountryRulesSchemaError, match="DocumentType"):
        load_rules_from_dir(tmp_path)


def test_missing_default_file_raises(tmp_path: Path) -> None:
    (tmp_path / "xx.yaml").write_text(_minimal_yaml("XX", "STANDARD"))

    with pytest.raises(CountryRulesSchemaError, match="Default rules file"):
        load_rules_from_dir(tmp_path)


def test_missing_country_code_raises() -> None:
    with pytest.raises(CountryRulesSchemaError, match="country_code"):
        _parse_rules({"country_name": "X", "fatf_status": "STANDARD"}, source="x.yaml")


def test_ubo_override_accepts_number_or_null() -> None:
    rules = _parse_rules(
        yaml.safe_load(
            "country_code: XX\n"
            "country_name: Test\n"
            "fatf_status: STANDARD\n"
            "ubo_threshold_override: 10.0\n"
        ),
        source="xx.yaml",
    )
    assert rules.ubo_threshold_override == 10.0


def test_ubo_override_string_rejected() -> None:
    with pytest.raises(CountryRulesSchemaError, match="ubo_threshold_override"):
        _parse_rules(
            {
                "country_code": "XX",
                "country_name": "Test",
                "fatf_status": "STANDARD",
                "ubo_threshold_override": "not-a-number",
            },
            source="xx.yaml",
        )


def _minimal_yaml(code: str, status: str) -> str:
    return (
        f"country_code: {code}\n"
        f"country_name: {code}\n"
        f"fatf_status: {status}\n"
        f"required_identity_doc_types:\n"
        f"  - PASSPORT\n"
        f"required_address_doc_types:\n"
        f"  - PROOF_OF_ADDRESS\n"
    )
