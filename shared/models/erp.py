from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any


def now(): return datetime.now(timezone.utc)

@dataclass(frozen=True)
class Category:
    id: str; name: str; parent_id: str|None=None; type: str|None=None; created_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class Product:
    id: str; name: str; sku: str; product_type: str; barcode: str|None=None
    selling_price: Decimal=Decimal('0'); default_cost: Decimal=Decimal('0'); warranty_days: int=0; reorder_level: Decimal=Decimal('0'); active: bool=True
@dataclass(frozen=True)
class ProductUnit:
    id: str; product_id: str; branch_id: str; imei1: str|None=None; imei2: str|None=None; serial_number: str|None=None
    purchase_cost: Decimal=Decimal('0'); refurbishing_cost: Decimal=Decimal('0'); direct_cost: Decimal=Decimal('0'); final_cost: Decimal=Decimal('0')
    selling_price: Decimal=Decimal('0'); condition: str='NEW'; battery_health: Decimal|None=None; physical_condition: str|None=None
    warranty_start: date|None=None; warranty_end: date|None=None; status: str='AVAILABLE'
@dataclass(frozen=True)
class Supplier:
    id: str; name: str; phone: str|None=None; branch_ids: tuple[str,...]=(); active: bool=True
@dataclass(frozen=True)
class Customer:
    id: str; name: str; phone: str|None=None; active: bool=True
@dataclass(frozen=True)
class StockMovement:
    id: str; branch_id: str; product_id: str; quantity: Decimal; movement_type: str; reference_id: str; unit_id: str|None=None; cost: Decimal=Decimal('0'); created_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class SaleItem:
    id: str; product_id: str; quantity: Decimal; unit_price: Decimal; cost_snapshot: Decimal=Decimal('0'); product_unit_id: str|None=None
@dataclass(frozen=True)
class Payment:
    id: str; sale_id: str; wallet_id: str; amount: Decimal
@dataclass(frozen=True)
class Sale:
    id: str; branch_id: str; customer_id: str|None; items: tuple[SaleItem,...]; subtotal: Decimal; discount: Decimal; total: Decimal; payments: tuple[Payment,...]; status: str='COMPLETED'; created_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class PurchaseItem:
    id: str; product_id: str; quantity: Decimal; unit_cost: Decimal; product_unit_id: str|None=None
@dataclass(frozen=True)
class Purchase:
    id: str; branch_id: str; supplier_id: str; items: tuple[PurchaseItem,...]; total: Decimal; paid: Decimal=Decimal('0'); status: str='COMPLETED'; created_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class Wallet:
    id: str; branch_id: str; name: str; wallet_type: str; active: bool=True
@dataclass(frozen=True)
class LedgerEntry:
    id: str; branch_id: str; account_id: str; entry_type: str; debit: Decimal=Decimal('0'); credit: Decimal=Decimal('0'); reference_id: str|None=None; reversal_of: str|None=None; created_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class Expense:
    id: str; branch_id: str; wallet_id: str; amount: Decimal; category: str; approved: bool=True; note: str|None=None
@dataclass(frozen=True)
class InstallmentPlan:
    id: str; sale_id: str; customer_id: str; base_financed: Decimal; rate_percent: Decimal; increase: Decimal; total_due: Decimal; term_months: int; monthly_amount: Decimal
@dataclass(frozen=True)
class InstallmentPayment:
    id: str; plan_id: str; amount: Decimal; wallet_id: str; paid_at: datetime=field(default_factory=now)
@dataclass(frozen=True)
class MaintenanceTicket:
    id: str; branch_id: str; customer_id: str; device: str; imei: str|None; problem: str; status: str='RECEIVED'; technician_id: str|None=None
    estimated_parts: Decimal=Decimal('0'); estimated_labor: Decimal=Decimal('0'); parts_cost: Decimal=Decimal('0'); final_cost: Decimal=Decimal('0'); payment: Decimal=Decimal('0'); warranty_eligible: bool=False
@dataclass(frozen=True)
class Employee:
    id: str; name: str; branch_ids: tuple[str,...]=(); salary_type: str='FIXED'; fixed_salary: Decimal=Decimal('0'); active: bool=True
@dataclass(frozen=True)
class SalaryRecord:
    id: str; employee_id: str; period: str; base: Decimal; commission: Decimal=Decimal('0'); bonus: Decimal=Decimal('0'); deductions: Decimal=Decimal('0'); paid: Decimal=Decimal('0')
@dataclass(frozen=True)
class DailyClosing:
    id: str; branch_id: str; closing_date: date; expected: dict[str,Decimal]; actual: dict[str,Decimal]; discrepancy: dict[str,Decimal]; locked: bool=False
