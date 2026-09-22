from shared.contracts.commands import CommandContext
from shared.contracts.errors import DomainError
from backend.functions.validators.permissions import require_permission

def authorize_purchase(ctx: CommandContext): require_permission(ctx.permissions,'purchases.create')
