from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from src.infra.orm import Base

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


@pytest.fixture
def alembic_config(tmp_path: Path) -> tuple[Config, Path]:
    db_path = tmp_path / "kyc-test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, db_path


def test_initial_migration_creates_all_tables(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())

    assert {"kyc_cases", "documents", "individual_applicants", "corporate_applicants"}.issubset(
        tables
    )
    assert "alembic_version" in tables


def test_initial_migration_downgrade_drops_all_tables(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())

    for t in ("kyc_cases", "documents", "individual_applicants", "corporate_applicants"):
        assert t not in tables


def test_documents_has_foreign_key_to_kyc_cases(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    fks = inspect(engine).get_foreign_keys("documents")

    assert any(
        fk["referred_table"] == "kyc_cases" and fk["referred_columns"] == ["id"]
        for fk in fks
    )


def test_kyc_cases_columns_match_orm_model(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    cols = {c["name"] for c in inspect(engine).get_columns("kyc_cases")}

    expected = {
        "id",
        "case_type",
        "country_code",
        "fund_id",
        "status",
        "risk_tier",
        "created_at",
        "updated_at",
        "reviewer_id",
        "rejection_reason",
        "expiry_date",
        "case_metadata",
    }
    assert cols == expected


def test_no_drift_between_orm_metadata_and_migration(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        diffs = compare_metadata(ctx, Base.metadata)

    assert diffs == [], f"Schema drift between ORM and migration: {diffs}"
