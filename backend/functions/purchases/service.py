from decimal import Decimal
from shared.models.erp import Purchase, PurchaseItem
from backend.functions.repositories.generic import Repository
from backend.functions.inventory.service import InventoryService
class PurchaseService:
    def __init__(self,purchases=None,inventory=None): self.repo=purchases or Repository(); self.inventory=inventory or InventoryService()
    def create(self,purchase): return self.repo.create(purchase.id,purchase)
    def total(self,items): return sum((i.quantity*i.unit_cost for i in items),Decimal('0'))
