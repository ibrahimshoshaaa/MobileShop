from decimal import Decimal
from shared.contracts.commands import CommandContext, TransferCommand
from backend.functions.commands.transfer import execute

def ctx(perms=("wallet.transfer",)):
    return CommandContext("cmd-1", "u-1", "b-1", frozenset(perms))

def test_default_one_percent_commission():
    result = execute(TransferCommand(ctx(), "cash", "wallet", Decimal("10000")))
    assert result["commission"] == Decimal("100.00")

def test_manual_commission_override():
    result = execute(TransferCommand(ctx(), "cash", "wallet", Decimal("10000"), Decimal("50")))
    assert result["commission"] == Decimal("50.00")
