from shared.contracts.errors import DomainError
from shared.models.foundation import User


def authorize_branch(user: User, branch_id: str) -> None:
    if branch_id not in user.branch_ids:
        raise DomainError("BRANCH_ACCESS_DENIED", "Branch access denied.")


def effective_permissions(user: User, role_permissions: dict[str, set[str]]) -> frozenset[str]:
    permissions: set[str] = set(user.permissions_override)
    for role in user.role_ids:
        permissions.update(role_permissions.get(role, set()))
    return frozenset(permissions)
