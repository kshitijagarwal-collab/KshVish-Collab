from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


@pytest.fixture
def alembic_config(tmp_path: Path) -> tuple[Config, Path]:
    db_path = tmp_path / "kyc-test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, db_path


def test_audit_events_table_created_at_revision_002(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "002")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert "audit_events" in tables


def test_audit_events_columns_present(alembic_config: tuple[Config, Path]) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    cols = {c["name"] for c in inspect(engine).get_columns("audit_events")}
    expected = {
        "id",
        "event_type",
        "case_id",
        "actor",
        "occurred_at",
        "applicant_id",
        "payload",
        "ip_address",
        "session_id",
    }
    assert cols == expected


def test_audit_events_indexes_present(alembic_config: tuple[Config, Path]) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    indexed_columns = {
        tuple(idx["column_names"])
        for idx in inspect(engine).get_indexes("audit_events")
    }
    assert ("case_id",) in indexed_columns
    assert ("event_type",) in indexed_columns
    assert ("occurred_at",) in indexed_columns


def test_downgrade_to_001_drops_audit_events(
    alembic_config: tuple[Config, Path],
) -> None:
    cfg, db_path = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "001")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert "audit_events" not in tables
    assert "kyc_cases" in tables
