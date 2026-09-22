"""Desktop expenses repository.

Deviation from shared/models/erp.py Expense (same one already documented on
the mobile side): the backend checks the expense against a real wallet
balance from the ledger before allowing it. Neither this desktop app nor the
mobile app model a wallet balance at all — payment method is recorded as a
category label, not a balance that moves — so no balance check happens here
either. This is not a new simplification introduced for desktop; it's the
same one already in place for mobile, kept for parity.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store
from sales_repo import PAYMENT_METHODS  # noqa: F401  (re-exported for the tab module)

ENTITY = "expense"

EXPENSE_CATEGORIES = ["إيجار", "كهرباء ومياه", "رواتب", "صيانة", "نقل وتوصيل", "أخرى"]


@dataclass
class Expense:
    id: str
    amount: float
    category: str
    method: str  # CASH / WALLET / CARD / CREDIT — see sales_repo.PAYMENT_METHODS
    note: str | None = None
    created_at: datetime | None = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


def _to_expense(payload: dict) -> Expense:
    return Expense(
        id=payload["id"], amount=float(payload["amount"]), category=payload["category"],
        method=payload["wallet_id"], note=payload.get("note"),
        created_at=datetime.fromisoformat(payload["created_at"]),
    )


def _to_payload(e: Expense) -> dict:
    return {
        "id": e.id, "amount": e.amount, "category": e.category, "wallet_id": e.method,
        "note": e.note, "created_at": e.created_at.isoformat(),
    }


def _new_id() -> str:
    return f"exp-{uuid.uuid4().hex[:12]}"


def list_expenses(since: datetime | None = None) -> list[Expense]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    expenses = sorted((_to_expense(r["payload"]) for r in rows), key=lambda e: e.created_at, reverse=True)
    if since is not None:
        expenses = [e for e in expenses if e.created_at >= since]
    return expenses


def add_expense(*, amount: float, category: str, method: str, note: str | None = None) -> Expense:
    if amount <= 0:
        raise AppError("قيمة المصروف يجب أن تكون موجبة.")
    if not category.strip():
        raise AppError("يجب اختيار تصنيف للمصروف.")
    expense = Expense(id=_new_id(), amount=amount, category=category, method=method,
                       note=(note.strip() if note and note.strip() else None))
    store = get_store()
    store.upsert_record(
        entity=ENTITY, record_id=expense.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(expense), expected_version=0,
    )
    store.submit_command(
        command_id=f"cmd-expense-{uuid.uuid4().hex[:12]}", tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="createExpense", payload={"wallet_id": method, "amount": amount, "category": category, "note": expense.note},
    )
    return expense


def total_for_today() -> float:
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(e.amount for e in list_expenses(since=start_of_day))
