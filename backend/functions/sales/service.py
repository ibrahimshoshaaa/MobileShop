from decimal import Decimal
from dataclasses import replace
from shared.models.erp import Sale,SaleItem,Payment,ProductUnit
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import Repository
from backend.functions.inventory.service import InventoryService
class SalesService:
    def __init__(self,sales=None,inventory=None): self.repo=sales or Repository(); self.inventory=inventory or InventoryService()
    def create(self,sale):
        if not sale.items: raise DomainError('INVALID_INPUT','الفاتورة بدون أصناف.',{})
        paid=sum((p.amount for p in sale.payments),Decimal('0'))
        if paid != sale.total: raise DomainError('INVALID_PAYMENT','إجمالي المدفوعات لا يساوي إجمالي الفاتورة.',{})
        for i in sale.items:
            if i.product_unit_id: self.inventory.assert_sellable(i.product_unit_id,sale.branch_id)
        return self.repo.create(sale.id,sale)
    def void(self,sale_id):
        s=self.repo.get(sale_id)
        if not s: raise DomainError('NOT_FOUND','الفاتورة غير موجودة.',{})
        if s.status=='VOIDED': raise DomainError('SALE_ALREADY_VOIDED','الفاتورة ملغاة بالفعل.',{})
        return self.repo.update(sale_id,replace(s,status='VOIDED'))
