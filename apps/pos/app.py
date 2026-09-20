"""Thin POS adapter: UI should call server commands, never write financial state."""
from shared.contracts.commands import CommandContext, CreateSaleCommand
class POSApp:
    def __init__(self, engine): self.engine=engine
    def checkout(self, context, customer_id, items, payments, discount=0):
        return self.engine.create_sale(CreateSaleCommand(context,customer_id,tuple(items),tuple(payments),discount))
