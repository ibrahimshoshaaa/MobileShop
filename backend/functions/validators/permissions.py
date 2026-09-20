from shared.contracts.errors import DomainError

def require_permission(permissions: frozenset[str], required: str) -> None:
    if required not in permissions:
        raise DomainError("FORBIDDEN", "غير مصرح لك بتنفيذ هذه العملية.", {"permission": required})

def require_any_permission(permissions: frozenset[str], required: set[str]) -> None:
    if not permissions.intersection(required):
        raise DomainError("FORBIDDEN", "غير مصرح لك بتنفيذ هذه العملية.", {"permissions": sorted(required)})
