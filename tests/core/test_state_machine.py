from __future__ import annotations
import pytest

from src.core.domain.kyc_case import CaseStatus
from src.core.workflow.state_machine import (
    InvalidTransitionError,
    TRANSITIONS,
    allowed_transitions,
    is_terminal,
    validate_transition,
)

# All valid transitions derived from the TRANSITIONS map
VALID_TRANSITIONS = [
    (CaseStatus.INITIATED, CaseStatus.DOCUMENTS_PENDING),
    (CaseStatus.INITIATED, CaseStatus.REJECTED),
    (CaseStatus.DOCUMENTS_PENDING, CaseStatus.IN_REVIEW),
    (CaseStatus.DOCUMENTS_PENDING, CaseStatus.REJECTED),
    (CaseStatus.DOCUMENTS_PENDING, CaseStatus.EXPIRED),
    (CaseStatus.IN_REVIEW, CaseStatus.APPROVED),
    (CaseStatus.IN_REVIEW, CaseStatus.REJECTED),
    (CaseStatus.IN_REVIEW, CaseStatus.PENDING_INFO),
    (CaseStatus.PENDING_INFO, CaseStatus.IN_REVIEW),
    (CaseStatus.PENDING_INFO, CaseStatus.REJECTED),
    (CaseStatus.PENDING_INFO, CaseStatus.EXPIRED),
    (CaseStatus.APPROVED, CaseStatus.EXPIRED),
]

INVALID_TRANSITIONS = [
    (CaseStatus.INITIATED, CaseStatus.APPROVED),
    (CaseStatus.INITIATED, CaseStatus.IN_REVIEW),
    (CaseStatus.INITIATED, CaseStatus.PENDING_INFO),
    (CaseStatus.INITIATED, CaseStatus.EXPIRED),
    (CaseStatus.DOCUMENTS_PENDING, CaseStatus.APPROVED),
    (CaseStatus.DOCUMENTS_PENDING, CaseStatus.PENDING_INFO),
    (CaseStatus.IN_REVIEW, CaseStatus.INITIATED),
    (CaseStatus.IN_REVIEW, CaseStatus.DOCUMENTS_PENDING),
    (CaseStatus.IN_REVIEW, CaseStatus.EXPIRED),
    (CaseStatus.APPROVED, CaseStatus.INITIATED),
    (CaseStatus.APPROVED, CaseStatus.APPROVED),
    (CaseStatus.REJECTED, CaseStatus.INITIATED),
    (CaseStatus.REJECTED, CaseStatus.IN_REVIEW),
    (CaseStatus.REJECTED, CaseStatus.APPROVED),
    (CaseStatus.EXPIRED, CaseStatus.INITIATED),
    (CaseStatus.EXPIRED, CaseStatus.APPROVED),
]


@pytest.mark.parametrize("current,next_status", VALID_TRANSITIONS)
def test_valid_transitions_do_not_raise(current, next_status):
    validate_transition(current, next_status)  # must not raise


@pytest.mark.parametrize("current,next_status", INVALID_TRANSITIONS)
def test_invalid_transitions_raise(current, next_status):
    with pytest.raises(InvalidTransitionError):
        validate_transition(current, next_status)


def test_terminal_states_are_rejected_and_expired():
    assert is_terminal(CaseStatus.REJECTED)
    assert is_terminal(CaseStatus.EXPIRED)


def test_non_terminal_states():
    for status in [
        CaseStatus.INITIATED,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.IN_REVIEW,
        CaseStatus.PENDING_INFO,
        CaseStatus.APPROVED,
    ]:
        assert not is_terminal(status)


def test_allowed_transitions_returns_correct_set():
    assert CaseStatus.DOCUMENTS_PENDING in allowed_transitions(CaseStatus.INITIATED)
    assert CaseStatus.REJECTED in allowed_transitions(CaseStatus.INITIATED)
    assert CaseStatus.APPROVED not in allowed_transitions(CaseStatus.INITIATED)


def test_allowed_transitions_on_terminal_returns_empty():
    assert allowed_transitions(CaseStatus.REJECTED) == set()
    assert allowed_transitions(CaseStatus.EXPIRED) == set()


def test_error_message_includes_allowed_transitions():
    with pytest.raises(InvalidTransitionError, match="APPROVED"):
        validate_transition(CaseStatus.INITIATED, CaseStatus.APPROVED)
