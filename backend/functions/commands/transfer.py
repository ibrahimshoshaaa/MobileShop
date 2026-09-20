from shared.contracts.commands import TransferCommand
from backend.functions.services.transfer_service import TransferService

def execute(command: TransferCommand) -> dict:
    # Phase 0: validate/prepare only. Phase 1 will wrap this in a Firestore transaction.
    return TransferService().prepare(command)
