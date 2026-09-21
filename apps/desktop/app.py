"""Desktop POS shell.

Ported from the mobile app's four working modules (inventory, sales,
customers, installments) — same validation rules, same local SQLite-backed
persistence pattern (via local_store.py, which reuses the production
backend/functions/persistence/sqlite_repository.py as-is). Each module keeps
its own file (inventory_repo.py / inventory_tab.py, etc.) mirroring the
Flutter feature-folder layout in apps/admin_mobile/lib/features/.

Online mode: set MOBILE_SHOP_ERP_MODE=online to make the Inventory tab talk
to a real backend/api_server instance (default http://localhost:8000) over
HTTP instead of the local SQLite file — see api_inventory_repo.py. This is
scoped to Inventory only for now; Sales and Maintenance still use their own
local product lookups (ProductPickerWindow defaults to offline inventory_repo)
even when Inventory itself is in online mode — wiring the rest of the tabs
the same way is a further increment, not done in this pass.

Configure the connection with:
    MOBILE_SHOP_ERP_MODE=online
    MOBILE_SHOP_ERP_API_URL=http://localhost:8000   (optional, this is the default)
    MOBILE_SHOP_ERP_API_TOKEN=dev-owner-token       (optional, this is the default)
"""
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow sibling imports (inventory_repo, etc.)

from customers_tab import CustomersTab  # noqa: E402
from expenses_tab import ExpensesTab  # noqa: E402
from installments_tab import InstallmentsTab  # noqa: E402
from inventory_tab import InventoryTab  # noqa: E402
from maintenance_tab import MaintenanceTab  # noqa: E402
from sales_tab import SalesTab  # noqa: E402
from suppliers_tab import SuppliersTab  # noqa: E402

ONLINE_MODE = os.environ.get("MOBILE_SHOP_ERP_MODE", "offline").strip().lower() == "online"


def _online_repositories():
    if not ONLINE_MODE:
        import sales_repo, inventory_repo, customers_repo
        return sales_repo, inventory_repo, customers_repo

    import api_client
    import api_sales_repo
    import api_inventory_repo
    import api_customers_repo
    api_client.DEFAULT_BASE_URL = os.environ.get("MOBILE_SHOP_ERP_API_URL", api_client.DEFAULT_BASE_URL)
    api_client.DEFAULT_TOKEN = os.environ.get("MOBILE_SHOP_ERP_API_TOKEN", api_client.DEFAULT_TOKEN)
    client = api_client.ApiClient(api_client.DEFAULT_BASE_URL, api_client.DEFAULT_TOKEN)
    api_sales_repo._client = client
    api_inventory_repo._client = client
    api_customers_repo._client = client
    return api_sales_repo, api_inventory_repo, api_customers_repo


class DesktopApp:
    def __init__(self, root):
        self.root = root
        root.title("Mobile Shop ERP - POS")
        root.geometry("1100x750")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        sales_repo_module, inventory_repo_module, customers_repo_module = _online_repositories()
        notebook.add(SalesTab(
            notebook,
            repo=sales_repo_module,
            inventory_repo_module=inventory_repo_module,
            customers_repo_module=customers_repo_module,
        ), text="المبيعات")
        notebook.add(InventoryTab(notebook, repo=inventory_repo_module), text="المخزون")
        notebook.add(CustomersTab(notebook), text="العملاء")
        notebook.add(SuppliersTab(notebook), text="الموردون")
        notebook.add(InstallmentsTab(notebook), text="الأقساط")
        notebook.add(MaintenanceTab(notebook), text="الصيانة")
        notebook.add(ExpensesTab(notebook), text="المصروفات")

        if ONLINE_MODE:
            api_url = os.environ.get("MOBILE_SHOP_ERP_API_URL", "http://localhost:8000")
            status_text = f"الوضع: متصل بالسيرفر (المخزون + المبيعات) — {api_url}"
            try:
                inventory_repo_module.list_products()
            except Exception as e:
                messagebox.showwarning(
                    "تعذّر الاتصال بالسيرفر",
                    f"شاشة المخزون في وضع 'متصل بالسيرفر' لكن الاتصال فشل:\n{e}\n\n"
                    "تأكد إن السيرفر شغّال (uvicorn backend.api_server.main:app) وحاول تاني.",
                )
        else:
            status_text = "الوضع: Offline | التخزين المحلي: SQLite | العمليات المعلقة تُحفظ في outbox محلي"

        status = ttk.Label(root, text=status_text)
        status.pack(fill="x", padx=12, pady=4)


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
