from src.core.domain.kyc_case import CaseStatus

# Valid transitions: from_status -> set of allowed to_statuses
TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.INITIATED: {
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.REJECTED,
    },
    CaseStatus.DOCUMENTS_PENDING: {
        CaseStatus.IN_REVIEW,
        CaseStatus.REJECTED,
        CaseStatus.EXPIRED,
    },
    CaseStatus.IN_REVIEW: {
        CaseStatus.APPROVED,
        CaseStatus.REJECTED,
        CaseStatus.PENDING_INFO,
    },
    CaseStatus.PENDING_INFO: {
        CaseStatus.IN_REVIEW,
        CaseStatus.REJECTED,
        CaseStatus.EXPIRED,
    },
    CaseStatus.APPROVED: {
        CaseStatus.EXPIRED,
    },
    CaseStatus.REJECTED: set(),
    CaseStatus.EXPIRED: set(),
}


class InvalidTransitionError(Exception):
    pass


def validate_transition(current: CaseStatus, next_status: CaseStatus) -> None:
    allowed = TRANSITIONS.get(current, set())
    if next_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {current} to {next_status}. "
            f"Allowed: {allowed or 'none (terminal state)'}"
        )


def allowed_transitions(current: CaseStatus) -> set[CaseStatus]:
    return TRANSITIONS.get(current, set())


def is_terminal(status: CaseStatus) -> bool:
    return not TRANSITIONS.get(status)
