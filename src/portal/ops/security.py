from __future__ import annotations

from src.api.auth.rbac import Role, require_role


require_ops_role = require_role(Role.REVIEWER, Role.ADMIN)
