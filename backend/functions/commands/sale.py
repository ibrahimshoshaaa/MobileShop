from shared.contracts.commands import CreateSaleCommand
from backend.functions.sales.service import SalesService

def execute(command: CreateSaleCommand, service=None):
    # Adapter/orchestration point; persistence transaction belongs here when Firebase adapter is connected.
    return (service or SalesService()).create(command)
