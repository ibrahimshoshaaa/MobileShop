from shared.contracts.commands import CollectInstallmentCommand
from backend.functions.installments.service import InstallmentService

def execute(command, service=None): return (service or InstallmentService()).collect(command)
