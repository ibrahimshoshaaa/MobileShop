from decimal import Decimal
from shared.contracts.errors import DomainError

def validate_wallet_transfer(amount):
    if Decimal(amount)<=0: raise DomainError('INVALID_INPUT','المبلغ يجب أن يكون أكبر من صفر.',{})
    return Decimal(amount)
