from decimal import Decimal
class ReportService:
    def sales_summary(self,sales):
        completed=[s for s in sales if s.status=='COMPLETED']; revenue=sum((s.total for s in completed),Decimal('0')); discount=sum((s.discount for s in completed),Decimal('0'))
        return {'count':len(completed),'revenue':revenue,'discount':discount}
    def inventory_value(self,units): return sum((u.final_cost for u in units if u.status in ('AVAILABLE','RESERVED','RETURNED')),Decimal('0'))
