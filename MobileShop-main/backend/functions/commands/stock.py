from decimal import Decimal
from shared.models.erp import StockMovement
from shared.contracts.errors import DomainError

def validate_quantity(q):
    if Decimal(q)<=0: raise DomainError('INVALID_INPUT','الكمية يجب أن تكون أكبر من صفر.',{})
    return Decimal(q)
