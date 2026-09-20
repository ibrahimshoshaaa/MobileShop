from dataclasses import replace
from shared.models.erp import MaintenanceTicket
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import Repository
class MaintenanceService:
    ALLOWED={'RECEIVED':'DIAGNOSING','DIAGNOSING':'WAITING_CUSTOMER','WAITING_CUSTOMER':'IN_PROGRESS','IN_PROGRESS':'READY','READY':'DELIVERED'}
    def __init__(self,repo=None): self.repo=repo or Repository()
    def create(self,t): return self.repo.create(t.id,t)
    def transition(self,ticket_id,status):
        t=self.repo.get(ticket_id)
        if not t: raise DomainError('NOT_FOUND','تذكرة الصيانة غير موجودة.',{})
        if status!='CANCELLED' and self.ALLOWED.get(t.status)!=status: raise DomainError('INVALID_INPUT','انتقال حالة الصيانة غير مسموح.',{})
        return self.repo.update(ticket_id,replace(t,status=status))
