from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime
from api_client import ApiClient
from errors import AppError

NEXT_STATUS={"RECEIVED":"DIAGNOSING","DIAGNOSING":"WAITING_CUSTOMER","WAITING_CUSTOMER":"IN_PROGRESS","IN_PROGRESS":"READY","READY":"DELIVERED"}
STATUS_LABELS={"RECEIVED":"تم الاستلام","DIAGNOSING":"جارِ الفحص","WAITING_CUSTOMER":"بانتظار العميل","IN_PROGRESS":"جارِ الإصلاح","READY":"جاهز للتسليم","DELIVERED":"تم التسليم","CANCELLED":"ملغي"}
@dataclass
class MaintenanceTicket:
    id:str; customer_id:str; customer_name:str; device:str; problem:str; imei:str|None=None; status:str="RECEIVED"; parts_cost:float=0.0; final_cost:float=0.0; payment:float=0.0; created_at:datetime|None=None
    @property
    def status_label(self): return STATUS_LABELS.get(self.status,self.status)
    @property
    def is_open(self): return self.status not in ("DELIVERED","CANCELLED")
    @property
    def next_status(self): return NEXT_STATUS.get(self.status)
@dataclass
class MaintenancePartUsage:
    id:str; ticket_id:str; product_id:str; product_name:str; quantity:int; cost:float; used_at:datetime|None=None
    @property
    def total(self): return self.quantity*self.cost
_client=ApiClient()

def _to_ticket(d): return MaintenanceTicket(id=d["id"],customer_id=d["customer_id"],customer_name=d.get("customer_name",d["customer_id"]),device=d["device"],problem=d["problem"],imei=d.get("imei"),status=d.get("status","RECEIVED"),parts_cost=float(d.get("parts_cost",0)),final_cost=float(d.get("final_cost",0)),payment=float(d.get("payment",0)),created_at=datetime.fromisoformat(d["created_at"].replace("Z","+00:00")) if d.get("created_at") else None)

def list_tickets():
    customers={c["id"]:c for c in _client.get_customers()}; out=[]
    for d in _client.get_entity("maintenance"):
        t=_to_ticket(d); t.customer_name=customers.get(t.customer_id,{}).get("name",t.customer_name); out.append(t)
    return sorted(out,key=lambda t:t.created_at or datetime.min,reverse=True)

def create_ticket(*,customer_id,customer_name,device,problem,imei=None):
    if not device.strip() or not problem.strip(): raise AppError("الجهاز ووصف المشكلة مطلوبان.")
    return _to_ticket(_client.command(f"cmd-mnt-{uuid.uuid4().hex[:12]}","createMaintenanceTicket",{"customer_id":customer_id,"device":device.strip(),"problem":problem.strip(),"imei":imei.strip() if imei and imei.strip() else None}))

def advance_status(ticket_id):
    t=next((x for x in list_tickets() if x.id==ticket_id),None)
    if not t or not t.next_status: raise AppError("لا يمكن نقل الحالة الحالية لمرحلة تالية.")
    return _to_ticket(_client.command(f"cmd-mnt-status-{uuid.uuid4().hex[:12]}","transitionMaintenance",{"ticket_id":ticket_id,"new_status":t.next_status}))

def cancel_ticket(ticket_id): return _to_ticket(_client.command(f"cmd-mnt-cancel-{uuid.uuid4().hex[:12]}","cancelMaintenance",{"ticket_id":ticket_id}))

def list_parts_used(ticket_id):
    rows=[x for x in _client.get_entity("maintenance-parts") if x.get("ticket_id")==ticket_id]
    return [MaintenancePartUsage(id=x["id"],ticket_id=x["ticket_id"],product_id=x["product_id"],product_name=x.get("product_name",x["product_id"]),quantity=int(float(x["quantity"])),cost=float(x["cost"]),used_at=datetime.fromisoformat(x["used_at"].replace("Z","+00:00"))) for x in rows]

def use_part(*,ticket_id,product_id,product_name,quantity,cost):
    if quantity<=0: raise AppError("الكمية يجب أن تكون أكبر من صفر.")
    return _client.command(f"cmd-mnt-part-{uuid.uuid4().hex[:12]}","useMaintenancePart",{"ticket_id":ticket_id,"product_id":product_id,"quantity":quantity,"cost":cost})

def _wallet_for_method(method):
    wanted={"CASH":"CASH","WALLET":"WALLET","CARD":"CARD"}.get(method)
    if not wanted: raise AppError("طريقة الدفع غير مدعومة.")
    w=next((x for x in _client.get_wallets() if x.get("active",True) and x.get("wallet_type")==wanted),None)
    if not w: raise AppError("لا توجد محفظة مفعّلة لطريقة الدفع المحددة.")
    return w["id"]

def deliver_ticket(*,ticket_id,final_price,payment,method):
    wid=_wallet_for_method(method) if payment>0 else None
    return _to_ticket(_client.command(f"cmd-mnt-deliver-{uuid.uuid4().hex[:12]}","deliverMaintenanceTicket",{"ticket_id":ticket_id,"final_price":final_price,"payment":payment,"wallet_id":wid}))
