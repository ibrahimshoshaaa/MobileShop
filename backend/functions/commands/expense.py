from decimal import Decimal
from shared.models.erp import Expense
from backend.functions.validators.money import require_non_negative

def validate_expense(e:Expense): require_non_negative(e.amount,'amount'); return e
