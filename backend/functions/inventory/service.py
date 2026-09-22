from decimal import Decimal
from shared.models.erp import ProductUnit, StockMovement
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import Repository
class InventoryService:
    def __init__(self, units=None, movements=None): self.units=units or Repository(); self.movements=movements or Repository()
    def register_unit(self,u):
        for x in self.units.all():
            if u.imei1 and u.imei1 in (x.imei1,x.imei2) or u.imei2 and u.imei2 in (x.imei1,x.imei2): raise DomainError('IMEI_ALREADY_EXISTS','رقم IMEI موجود بالفعل.',{})
        if u.final_cost != u.purchase_cost+u.refurbishing_cost+u.direct_cost: u=ProductUnit(**{**u.__dict__,'final_cost':u.purchase_cost+u.refurbishing_cost+u.direct_cost})
        return self.units.create(u.id,u)
    def assert_sellable(self, unit_id, branch_id):
        u=self.units.get(unit_id)
        if not u: raise DomainError('NOT_FOUND','الوحدة غير موجودة.',{})
        if u.branch_id != branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة ليست في الفرع الحالي.',{})
        if u.status == 'SOLD': raise DomainError('IMEI_ALREADY_SOLD','هذا الـIMEI تم بيعه بالفعل.',{})
        if u.status != 'AVAILABLE': raise DomainError('INVALID_INPUT','الوحدة غير متاحة للبيع.',{})
        return u
    def record(self,m): return self.movements.create(m.id,m)
