"""Framework-neutral secure command entrypoint.

Production adapters MUST supply trusted server-side auth claims. The HTTP body is
never allowed to choose permissions or branch access. Firebase callable/HTTP
handlers should verify the ID token and derive uid/permissions/branch_ids from
server-side claims or the users collection before calling ``handle``.
"""
from shared.contracts.errors import DomainError
from shared.contracts.commands import CommandContext


def handle(request, engine, auth_verifier):
    data = request.get_json(silent=True) if hasattr(request, 'get_json') else request
    data = data or {}
    if not isinstance(data, dict):
        raise DomainError('INVALID_INPUT', 'بيانات الطلب غير صحيحة.', {})
    if not data.get('commandId') or not data.get('command'):
        raise DomainError('INVALID_INPUT', 'معرّف الأمر واسم الأمر مطلوبان.', {})
    if not isinstance(data['commandId'], str) or len(data['commandId']) > 128:
        raise DomainError('INVALID_INPUT', 'معرّف الأمر غير صالح.', {})
    if not isinstance(data['command'], str) or len(data['command']) > 64:
        raise DomainError('INVALID_INPUT', 'اسم الأمر غير صالح.', {})
    if not isinstance(data.get('payload', {}), dict):
        raise DomainError('INVALID_INPUT', 'بيانات الأمر غير صحيحة.', {})
    # Identity and authorization are derived exclusively from verified claims.
    for forbidden in ('tenant_id', 'tenantId', 'user_id', 'userId', 'permissions', 'auth'):
        if forbidden in data:
            raise DomainError('INVALID_INPUT', 'بيانات الهوية والصلاحيات لا تُقبل من جسم الطلب.', {'field': forbidden})

    # auth_verifier is trusted server code. It must return only authenticated,
    # server-derived claims and MUST NOT trust permissions from request payload.
    claims = auth_verifier(request)
    if not claims or not claims.get('uid'):
        raise DomainError('UNAUTHORIZED', 'تسجيل الدخول مطلوب.', {})

    branch_id = data.get('branchId')
    allowed_branches = frozenset(claims.get('branch_ids', ()))
    if not branch_id or branch_id not in allowed_branches:
        raise DomainError('BRANCH_ACCESS_DENIED', 'لا يمكن الوصول إلى هذا الفرع.', {'branch_id': branch_id})

    tenant_id = claims.get('tenant_id')
    if not tenant_id:
        raise DomainError('TENANT_REQUIRED', 'هوية المستأجر مطلوبة.', {})
    permissions = frozenset(claims.get('permissions', ()))
    ctx = CommandContext(data['commandId'], claims['uid'], branch_id, permissions, str(tenant_id))
    try:
        from .dispatch import dispatch
        result = dispatch(engine, data['command'], ctx, **data.get('payload', {}))
        return {'ok': True, 'data': result}
    except DomainError as exc:
        return {'ok': False, 'error': exc.as_dict()}
