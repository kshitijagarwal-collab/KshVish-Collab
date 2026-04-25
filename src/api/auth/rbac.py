from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, status

from .jwt import Principal, get_current_principal


class Role(str, Enum):
    REVIEWER = "REVIEWER"
    ADMIN = "ADMIN"
    APPLICANT = "APPLICANT"


def require_role(*roles: Role) -> Callable[..., Principal]:
    if not roles:
        raise ValueError("require_role(): at least one role must be specified")
    allowed = {r.value for r in roles}

    def _checker(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not allowed.intersection(principal.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return principal

    return _checker
