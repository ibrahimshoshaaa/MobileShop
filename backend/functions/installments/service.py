from decimal import Decimal, ROUND_HALF_UP
from dataclasses import replace
from shared.models.erp import InstallmentPlan, InstallmentPayment
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import Repository
class InstallmentService:
    def __init__(self, plans=None, payments=None): self.plans=plans or Repository(); self.payments=payments or Repository()
    def calculate(self, price, down_payment, rate_percent, term_months):
        if term_months<=0 or down_payment<0 or down_payment>price: raise DomainError('INVALID_INSTALLMENT_TERM','شروط التقسيط غير صحيحة.',{})
        base=price-down_payment; inc=(base*rate_percent/Decimal('100')).quantize(Decimal('.01'),ROUND_HALF_UP); total=base+inc
        monthly=(total/Decimal(term_months)).quantize(Decimal('.01'),ROUND_HALF_UP)
        return base,inc,total,monthly
    def create(self, plan): return self.plans.create(plan.id,plan)
    def collect(self,payment):
        plan=self.plans.get(payment.plan_id)
        if not plan: raise DomainError('NOT_FOUND','خطة التقسيط غير موجودة.',{})
        paid=sum((p.amount for p in self.payments.all() if p.plan_id==plan.id),Decimal('0'))
        if paid+payment.amount>plan.total_due: raise DomainError('INVALID_PAYMENT','المبلغ يتجاوز المتبقي.',{})
        return self.payments.create(payment.id,payment)
    def remaining(self,plan_id):
        p=self.plans.get(plan_id); paid=sum((x.amount for x in self.payments.all() if x.plan_id==plan_id),Decimal('0')); return p.total_due-paid if p else Decimal('0')
