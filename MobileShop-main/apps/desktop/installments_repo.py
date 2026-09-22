from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

PLAN_ENTITY = "installment_plan"
PAYMENT_ENTITY = "installment_payment"


@dataclass
class InstallmentPlan:
    id: str
    customer_id: str
    customer_name: str
    base_financed: float
    rate_percent: float
    increase: float
    total_due: float
    term_months: int
    monthly_amount: float
    sale_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InstallmentPayment:
    id: str
    plan_id: str
    amount: float
    method: str
    paid_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _round2(value: float) -> float:
    return round(value * 100) / 100


def calculate(*, price: float, down_payment: float, rate_percent: float, term_months: int) -> dict:
    """Mirrors InstallmentService.calculate in backend/functions/installments/service.py.

    Uses plain floats (rounded to 2 decimals), not the backend's Decimal —
    fine for typical shop prices, but not the same exact-decimal guarantee;
    a server-side recompute should be the final word once the API exists.
    """
    if term_months <= 0:
        raise AppError("عدد الأشهر يجب أن يكون أكبر من صفر.")
    if down_payment < 0:
        raise AppError("المقدم لا يمكن أن يكون سالبًا.")
    if down_payment > price:
        raise AppError("المقدم أكبر من السعر الإجمالي.")

    base = price - down_payment
    increase = _round2(base * rate_percent / 100)
    total = base + increase
    monthly = _round2(total / term_months)
    return {"base_financed": base, "increase": increase, "total_due": total, "monthly_amount": monthly}


def _plan_to_payload(p: InstallmentPlan) -> dict:
    return {
        "id": p.id,
        "sale_id": p.sale_id,
        "customer_id": p.customer_id,
        "customer_name": p.customer_name,
        "base_financed": p.base_financed,
        "rate_percent": p.rate_percent,
        "increase": p.increase,
        "total_due": p.total_due,
        "term_months": p.term_months,
        "monthly_amount": p.monthly_amount,
        "created_at": p.created_at.isoformat(),
    }


def _plan_from_payload(m: dict) -> InstallmentPlan:
    return InstallmentPlan(
        id=m["id"], sale_id=m.get("sale_id"), customer_id=m["customer_id"], customer_name=m["customer_name"],
        base_financed=float(m["base_financed"]), rate_percent=float(m["rate_percent"]), increase=float(m["increase"]),
        total_due=float(m["total_due"]), term_months=int(m["term_months"]), monthly_amount=float(m["monthly_amount"]),
        created_at=datetime.fromisoformat(m["created_at"]),
    )


def _payment_to_payload(p: InstallmentPayment) -> dict:
    return {"id": p.id, "plan_id": p.plan_id, "amount": p.amount, "wallet_id": p.method, "paid_at": p.paid_at.isoformat()}


def _payment_from_payload(m: dict) -> InstallmentPayment:
    return InstallmentPayment(
        id=m["id"], plan_id=m["plan_id"], amount=float(m["amount"]), method=m["wallet_id"],
        paid_at=datetime.fromisoformat(m["paid_at"]),
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def list_plans() -> list[InstallmentPlan]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=PLAN_ENTITY)
    return sorted((_plan_from_payload(r["payload"]) for r in rows), key=lambda p: p.created_at, reverse=True)


def create_plan(*, customer_id: str, customer_name: str, price: float, down_payment: float,
                 rate_percent: float, term_months: int, sale_id: str | None = None, down_payment_method: str = "CASH") -> InstallmentPlan:
    calc = calculate(price=price, down_payment=down_payment, rate_percent=rate_percent, term_months=term_months)
    plan = InstallmentPlan(
        id=_new_id("plan"), sale_id=sale_id, customer_id=customer_id, customer_name=customer_name,
        base_financed=calc["base_financed"], rate_percent=rate_percent, increase=calc["increase"],
        total_due=calc["total_due"], term_months=term_months, monthly_amount=calc["monthly_amount"],
    )
    store = get_store()
    store.upsert_record(
        entity=PLAN_ENTITY, record_id=plan.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_plan_to_payload(plan), expected_version=0,
    )
    store.submit_command(
        command_id=_new_id("cmd-plan"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="createInstallmentPlan", payload=_plan_to_payload(plan),
    )
    return plan


def list_payments(plan_id: str) -> list[InstallmentPayment]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=PAYMENT_ENTITY)
    payments = [_payment_from_payload(r["payload"]) for r in rows]
    return sorted((p for p in payments if p.plan_id == plan_id), key=lambda p: p.paid_at)


def remaining(plan_id: str) -> float:
    store = get_store()
    row = store.get_record(entity=PLAN_ENTITY, record_id=plan_id, tenant_id=DEFAULT_TENANT_ID)
    if row is None:
        raise AppError("خطة التقسيط غير موجودة.")
    plan = _plan_from_payload(row["payload"])
    paid = sum(p.amount for p in list_payments(plan_id))
    left = plan.total_due - paid
    return max(left, 0.0)


def collect_payment(*, plan_id: str, amount: float, method: str) -> InstallmentPayment:
    if amount <= 0:
        raise AppError("المبلغ يجب أن يكون أكبر من صفر.")
    store = get_store()
    row = store.get_record(entity=PLAN_ENTITY, record_id=plan_id, tenant_id=DEFAULT_TENANT_ID)
    if row is None:
        raise AppError("خطة التقسيط غير موجودة.")
    current_remaining = remaining(plan_id)
    if amount - current_remaining > 0.01:
        raise AppError(f"المبلغ يتجاوز المتبقي ({current_remaining:.2f} ج.م).")
    payment = InstallmentPayment(id=_new_id("inst-pay"), plan_id=plan_id, amount=amount, method=method)
    store.upsert_record(
        entity=PAYMENT_ENTITY, record_id=payment.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_payment_to_payload(payment), expected_version=0,
    )
    store.submit_command(
        command_id=_new_id("cmd-collect"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="collectInstallment", payload={"installment_id": plan_id, "amount": amount, "wallet_id": method},
    )
    return payment
