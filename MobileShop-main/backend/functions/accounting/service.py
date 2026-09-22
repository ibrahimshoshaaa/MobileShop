from decimal import Decimal
from backend.functions.repositories.generic import Repository
from shared.models.erp import LedgerEntry
class LedgerService:
    def __init__(self, repo=None): self.repo=repo or Repository()
    def post(self,e): return self.repo.create(e.id,e)
    def balance(self,account_id): return sum((x.debit-x.credit for x in self.repo.all() if x.account_id==account_id),Decimal('0'))
    def statement(self,account_id): return [x for x in self.repo.all() if x.account_id==account_id]
