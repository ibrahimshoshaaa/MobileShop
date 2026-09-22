"""Security helpers and production integration contract."""
from shared.contracts.errors import DomainError


def verify_claims(claims: dict) -> dict:
    """Validate already-verified Firebase/server claims.

    Token signature verification belongs to the Firebase Admin SDK adapter.
    This function rejects missing identity and malformed authorization claims.
    """
    if not isinstance(claims, dict) or not claims.get('uid'):
        raise DomainError('UNAUTHORIZED', 'تسجيل الدخول مطلوب.', {})
    branches = claims.get('branch_ids', ())
    permissions = claims.get('permissions', ())
    if isinstance(branches, str) or isinstance(permissions, str):
        raise DomainError('UNAUTHORIZED', 'بيانات الصلاحيات غير صحيحة.', {})
    return {'uid': str(claims['uid']), 'branch_ids': tuple(branches), 'permissions': tuple(permissions)}
