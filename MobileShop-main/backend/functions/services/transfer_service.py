from decimal import Decimal
from shared.contracts.commands import TransferCommand
from backend.functions.transfers.commission import calculate_commission
from backend.functions.validators.money import require_non_negative
from backend.functions.validators.permissions import require_permission

class TransferService:
    """Business boundary. Persistence/Firestore transaction is intentionally injected later."""

    def prepare(self, command: TransferCommand) -> dict:
        require_permission(command.context.permissions, "wallet.transfer")
        amount = require_non_negative(command.amount, "amount")
        commission = calculate_commission(amount, override=command.commission)
        return {
            "commandId": command.context.command_id,
            "branchId": command.context.branch_id,
            "sourceWalletId": command.source_wallet_id,
            "destinationWalletId": command.destination_wallet_id,
            "amount": amount,
            "commission": commission,
            "reference": command.reference,
        }
