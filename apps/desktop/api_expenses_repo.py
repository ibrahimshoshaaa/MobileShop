from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime
from api_client import ApiClient
from errors import AppError
from expenses_repo import EXPENSE_CATEGORIES
from sales_repo import PAYMENT_METHODS

@dataclass
class Expense:
    id: str; amount: float; category: str; method: str; note: str|None=None; created_at: datetime|None=None
_client=ApiClient()

def _wallet_for_method(method):
    wanted={"CASH":"CASH","WALLET":"WALLET","CARD":"CARD"}.get(method)
    if wanted is None: raise AppError("طريقة الدفع غير مدعومة للمصروفات.")
    wallets=_client.get_wallets()
    w=next((x for x in wallets if x.get("active",True) and x.get("wallet_type")==wanted),None)
    if not w: raise AppError("لا توجد محفظة مفعّلة من النوع المحدد على السيرفر.")
    return w["id"]

def _to_expense(d):
    return Expense(id=d["id"],amount=float(d["amount"]),category=d["category"],method=d.get("wallet_id",d.get("method","")),note=d.get("note"),created_at=datetime.fromisoformat(d["created_at"].replace("Z","+00:00")) if d.get("created_at") else None)

def list_expenses():
    wallets={w["id"]:w for w in _client.get_wallets()}
    out=[]
    for d in _client.get_entity("expenses"):
        e=_to_expense(d); w=wallets.get(e.method,{}); e.method=w.get("wallet_type",e.method); out.append(e)
    return out

def total_for_today():
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc).date()
    return sum(e.amount for e in list_expenses() if e.created_at and e.created_at.date()==now)

def add_expense(*,amount:float,category:str,method:str,note:str|None=None):
    if amount<=0: raise AppError("قيمة المصروف يجب أن تكون موجبة.")
    wallet_id=_wallet_for_method(method)
    return _to_expense(_client.command(f"cmd-expense-{uuid.uuid4().hex[:12]}","createExpense",{"wallet_id":wallet_id,"amount":amount,"category":category,"note":note or None}))
