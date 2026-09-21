"""Desktop POS shell.

Ported from the mobile app's four working modules (inventory, sales,
customers, installments) — same validation rules, same local SQLite-backed
persistence pattern (via local_store.py, which reuses the production
backend/functions/persistence/sqlite_repository.py as-is). Each module keeps
its own file (inventory_repo.py / inventory_tab.py, etc.) mirroring the
Flutter feature-folder layout in apps/admin_mobile/lib/features/.

Online mode: set MOBILE_SHOP_ERP_MODE=online to make the Inventory and Sales
surfaces talk to a real backend/api_server instance (default
http://localhost:8000) over HTTP instead of local SQLite. Sales uses
api_sales_repo.py plus the server's customers/wallets read endpoints. The
remaining desktop tabs stay offline until integrated one surface at a time.

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

from access_tab import AccessTab
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
        import suppliers_repo, expenses_repo, installments_repo, maintenance_repo
        return (sales_repo, inventory_repo, customers_repo, suppliers_repo, expenses_repo, installments_repo, maintenance_repo)

    import api_client
    import api_sales_repo
    import api_inventory_repo
    import api_customers_repo
    import api_suppliers_repo
    import api_expenses_repo
    import api_installments_repo
    import api_maintenance_repo
    import api_access_repo
    api_client.DEFAULT_BASE_URL = os.environ.get("MOBILE_SHOP_ERP_API_URL", api_client.DEFAULT_BASE_URL)
    api_client.DEFAULT_TOKEN = os.environ.get("MOBILE_SHOP_ERP_API_TOKEN", api_client.DEFAULT_TOKEN)
    branch_id = os.environ.get("MOBILE_SHOP_ERP_BRANCH_ID", api_client.DEFAULT_BRANCH_ID)
    client = api_client.ApiClient(api_client.DEFAULT_BASE_URL, api_client.DEFAULT_TOKEN, branch_id)
    api_sales_repo._client = client
    api_inventory_repo._client = client
    api_customers_repo._client = client
    api_suppliers_repo._client = client
    api_expenses_repo._client = client
    api_installments_repo._client = client
    api_maintenance_repo._client = client
    api_access_repo._client = client
    return (api_sales_repo, api_inventory_repo, api_customers_repo, api_suppliers_repo, api_expenses_repo, api_installments_repo, api_maintenance_repo)


class DesktopApp:
    def __init__(self, root):
        self.root = root
        root.title("Mobile Shop ERP - POS")
        root.geometry("1100x750")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        sales_repo_module, inventory_repo_module, customers_repo_module, suppliers_repo_module, expenses_repo_module, installments_repo_module, maintenance_repo_module = _online_repositories()
        notebook.add(SalesTab(
            notebook,
            repo=sales_repo_module,
            inventory_repo_module=inventory_repo_module,
            customers_repo_module=customers_repo_module,
        ), text="المبيعات")
        notebook.add(InventoryTab(notebook, repo=inventory_repo_module), text="المخزون")
        notebook.add(CustomersTab(notebook, repo=customers_repo_module), text="العملاء")
        notebook.add(SuppliersTab(notebook, repo=suppliers_repo_module), text="الموردون")
        notebook.add(InstallmentsTab(notebook, repo=installments_repo_module, customers_repo_module=customers_repo_module), text="الأقساط")
        notebook.add(MaintenanceTab(notebook, repo=maintenance_repo_module, customers_repo_module=customers_repo_module, inventory_repo_module=inventory_repo_module), text="الصيانة")
        notebook.add(ExpensesTab(notebook, repo=expenses_repo_module), text="المصروفات")
        if ONLINE_MODE:
            import api_access_repo
            notebook.add(AccessTab(notebook, repo=api_access_repo), text="الفروع والصلاحيات")

        if ONLINE_MODE:
            api_url = os.environ.get("MOBILE_SHOP_ERP_API_URL", "http://localhost:8000")
            status_text = f"الوضع: متصل بالسيرفر (Online) — {api_url}"
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
