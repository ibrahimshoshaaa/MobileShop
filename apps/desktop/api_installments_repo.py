from __future__ import annotations
import uuid
from dataclasses import dataclass,field
from datetime import datetime
from api_client import ApiClient
from errors import AppError

@dataclass
class InstallmentPlan:
    id:str; customer_id:str; customer_name:str; base_financed:float; rate_percent:float; increase:float; total_due:float; term_months:int; monthly_amount:float; sale_id:str|None=None; created_at:datetime=field(default_factory=datetime.now)
@dataclass
class InstallmentPayment:
    id:str; plan_id:str; amount:float; method:str; paid_at:datetime=field(default_factory=datetime.now)
_client=ApiClient()

def _round2(v): return round(v*100)/100

def calculate(*,price,down_payment,rate_percent,term_months):
    if term_months<=0: raise AppError("عدد الأشهر يجب أن يكون أكبر من صفر.")
    if down_payment<0 or down_payment>price: raise AppError("المقدم غير صحيح.")
    base=price-down_payment; inc=_round2(base*rate_percent/100); total=base+inc; monthly=_round2(total/term_months)
    return {"base_financed":base,"increase":inc,"total_due":total,"monthly_amount":monthly}

def _to_plan(d):
    return InstallmentPlan(id=d["id"],sale_id=d.get("sale_id"),customer_id=d["customer_id"],customer_name=d.get("customer_name",d["customer_id"]),base_financed=float(d["base_financed"]),rate_percent=float(d["rate_percent"]),increase=float(d["increase"]),total_due=float(d["total_due"]),term_months=int(d["term_months"]),monthly_amount=float(d["monthly_amount"]),created_at=datetime.fromisoformat(d["created_at"].replace("Z","+00:00")) if d.get("created_at") else datetime.now())

def list_plans():
    customers={c["id"]:c for c in _client.get_customers()}
    out=[]
    for d in _client.get_entity("installments"):
        p=_to_plan(d); p.customer_name=customers.get(p.customer_id,{}).get("name",p.customer_name); out.append(p)
    return sorted(out,key=lambda p:p.created_at,reverse=True)

def _wallet_for_payment(method):
    wanted={"CASH":"CASH","WALLET":"WALLET","CARD":"CARD"}.get(method)
    if not wanted: raise AppError("طريقة الدفع غير مدعومة.")
    w=next((x for x in _client.get_wallets() if x.get("active",True) and x.get("wallet_type")==wanted),None)
    if not w: raise AppError("لا توجد محفظة مفعّلة لطريقة الدفع المحددة.")
    return w["id"]

def _payments(plan_id):
    # The public query endpoint exposes the primary installment repository;
    # payment rows are retrieved through the dedicated API endpoint added below.
    rows=[x for x in _client.get_entity("installment-payments") if x.get("plan_id")==plan_id]
    return [InstallmentPayment(id=x["id"],plan_id=x["plan_id"],amount=float(x["amount"]),method=x["wallet_id"],paid_at=datetime.fromisoformat(x["paid_at"].replace("Z","+00:00"))) for x in rows]

def list_payments(plan_id): return _payments(plan_id)
def remaining(plan_id):
    p=next((x for x in list_plans() if x.id==plan_id),None)
    if not p: raise AppError("خطة التقسيط غير موجودة.")
    return max(0.0,p.total_due-sum(x.amount for x in _payments(plan_id)))

def create_plan(*,customer_id,customer_name,price,down_payment,rate_percent,term_months,sale_id=None):
    if not sale_id: raise AppError("التقسيط Online يحتاج رقم فاتورة مرتبطة.")
    wallet_id=None
    if down_payment>0: wallet_id=_wallet_for_payment("CASH")
    d=_client.command(f"cmd-plan-{uuid.uuid4().hex[:12]}","createInstallmentPlan",{"sale_id":sale_id,"customer_id":customer_id,"down_payment":down_payment,"rate_percent":rate_percent,"term_months":term_months,"down_payment_wallet_id":wallet_id})
    return _to_plan(d)

def collect_payment(*,plan_id,amount,method):
    if amount<=0: raise AppError("المبلغ يجب أن يكون أكبر من صفر.")
    wid=_wallet_for_payment(method)
    return _client.command(f"cmd-collect-{uuid.uuid4().hex[:12]}","collectInstallment",{"installment_id":plan_id,"amount":amount,"wallet_id":wid})
