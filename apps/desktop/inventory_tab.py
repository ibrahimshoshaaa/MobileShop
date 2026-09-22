"""Inventory tab for the desktop POS — Tkinter port of the mobile inventory screens.

Every class here takes an optional `repo` module (defaulting to the local
`inventory_repo` module) so the exact same UI works against either the
local SQLite store or api_inventory_repo (real HTTP calls to
backend/api_server) — see app.py's online/offline mode switch. Both modules
expose the same function signatures (list_products/add_product/
update_product/adjust_stock) and the same Product/PRODUCT_TYPES constants,
so nothing here needs to know which one it's talking to.
"""
import tkinter as tk
from tkinter import messagebox, ttk

import inventory_repo
from errors import AppError

ALL_TYPES_LABEL = "كل الأنواع"


class InventoryTab(ttk.Frame):
    def __init__(self, master, repo=inventory_repo):
        super().__init__(master)
        self.repo = repo
        self._build()
        self.reload()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=8)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        search_entry.pack(side="right", padx=4)
        search_entry.bind("<KeyRelease>", lambda e: self.reload())
        ttk.Label(bar, text="بحث:").pack(side="right", padx=4)

        self.type_var = tk.StringVar(value=ALL_TYPES_LABEL)
        type_values = [ALL_TYPES_LABEL] + [label for _, label in self.repo.PRODUCT_TYPES]
        type_combo = ttk.Combobox(bar, textvariable=self.type_var, values=type_values, state="readonly", width=18)
        type_combo.pack(side="right", padx=4)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self.reload())

        ttk.Button(bar, text="إضافة صنف", command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="تعديل", command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="تعديل الرصيد", command=self._adjust_selected).pack(side="left", padx=4)

        columns = ("name", "sku", "type", "price", "qty")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [
            ("name", "الاسم", 220), ("sku", "SKU", 140), ("type", "النوع", 140),
            ("price", "سعر البيع", 100), ("qty", "الكمية", 80),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.tag_configure("low_stock", background="#fde2e2")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(fill="x", padx=12, pady=4)

    def _type_code(self):
        label = self.type_var.get()
        if label == ALL_TYPES_LABEL:
            return None
        for code, text in self.repo.PRODUCT_TYPES:
            if text == label:
                return code
        return None

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        try:
            products = self.repo.list_products(product_type=self._type_code(), query=self.search_var.get())
        except AppError as e:
            messagebox.showerror("خطأ في الاتصال", e.message)
            self.status_label.config(text="تعذّر تحميل الأصناف")
            return
        for p in products:
            tags = ("low_stock",) if p.is_low_stock else ()
            self.tree.insert("", "end", iid=p.id, values=(p.name, p.sku, p.type_label, f"{p.selling_price:.2f}", p.quantity), tags=tags)
        self.status_label.config(text=f"عدد الأصناف المعروضة: {len(products)}")

    def _selected_product(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("تنبيه", "اختر صنفًا أولًا.")
            return None
        products = {p.id: p for p in self.repo.list_products()}
        return products.get(selection[0])

    def _add(self):
        ProductFormWindow(self, on_saved=self.reload, repo=self.repo)

    def _edit_selected(self):
        product = self._selected_product()
        if product:
            ProductFormWindow(self, existing=product, on_saved=self.reload, repo=self.repo)

    def _adjust_selected(self):
        product = self._selected_product()
        if product:
            StockAdjustWindow(self, product, on_saved=self.reload, repo=self.repo)


class ProductFormWindow(tk.Toplevel):
    def __init__(self, master, existing=None, on_saved=None, repo=inventory_repo):
        super().__init__(master)
        self.existing = existing
        self.on_saved = on_saved
        self.repo = repo
        self.title("تعديل صنف" if existing else "إضافة صنف جديد")
        self.geometry("380x480")
        self.resizable(False, False)
        self._build()
        self.grab_set()

    def _build(self):
        p = self.existing
        pad = {"padx": 12, "pady": 6}

        ttk.Label(self, text="نوع الصنف").pack(anchor="e", **pad)
        self.type_var = tk.StringVar(value=self.repo.PRODUCT_TYPE_LABELS[p.product_type] if p else self.repo.PRODUCT_TYPES[0][1])
        ttk.Combobox(self, textvariable=self.type_var, values=[t for _, t in self.repo.PRODUCT_TYPES], state="readonly").pack(fill="x", **pad)

        self.name_var = tk.StringVar(value=p.name if p else "")
        self.sku_var = tk.StringVar(value=p.sku if p else "")
        self.barcode_var = tk.StringVar(value=(p.barcode or "") if p else "")
        self.price_var = tk.StringVar(value=str(p.selling_price) if p else "")
        self.cost_var = tk.StringVar(value=str(p.default_cost) if p else "")
        self.reorder_var = tk.StringVar(value=str(p.reorder_level) if p else "0")
        self.qty_var = tk.StringVar(value=str(p.quantity) if p else "0")
        self.active_var = tk.BooleanVar(value=p.active if p else True)

        for label, var, state in [
            ("اسم الصنف", self.name_var, "normal"),
            ("رمز الصنف (SKU)", self.sku_var, "normal"),
            ("الباركود (اختياري)", self.barcode_var, "normal"),
            ("سعر البيع", self.price_var, "normal"),
            ("التكلفة", self.cost_var, "normal"),
            ("حد إعادة الطلب", self.reorder_var, "normal"),
            ("الكمية الافتتاحية" if not p else "الكمية (عدّلها من تعديل الرصيد)", self.qty_var, "normal" if not p else "disabled"),
        ]:
            ttk.Label(self, text=label).pack(anchor="e", **pad)
            ttk.Entry(self, textvariable=var, state=state).pack(fill="x", **pad)

        if p:
            ttk.Checkbutton(self, text="الصنف مفعّل", variable=self.active_var).pack(anchor="e", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)

        ttk.Button(self, text="حفظ" if p else "إضافة", command=self._submit).pack(pady=12)

    def _type_code(self):
        for code, label in self.repo.PRODUCT_TYPES:
            if label == self.type_var.get():
                return code
        return self.repo.PRODUCT_TYPES[0][0]

    def _submit(self):
        try:
            selling_price = float(self.price_var.get())
            default_cost = float(self.cost_var.get())
            reorder_level = int(self.reorder_var.get())
        except ValueError:
            self.error_label.config(text="تأكد من إدخال أرقام صحيحة للسعر والتكلفة وحد إعادة الطلب.")
            return

        try:
            if self.existing:
                updated = self.repo.Product(
                    id=self.existing.id, name=self.name_var.get().strip(), sku=self.sku_var.get().strip(),
                    product_type=self._type_code(),
                    barcode=self.barcode_var.get().strip() or None,
                    selling_price=selling_price, default_cost=default_cost, reorder_level=reorder_level,
                    quantity=self.existing.quantity, active=self.active_var.get(),
                )
                self.repo.update_product(updated)
            else:
                opening_quantity = int(self.qty_var.get())
                self.repo.add_product(
                    name=self.name_var.get(), sku=self.sku_var.get(), product_type=self._type_code(),
                    barcode=self.barcode_var.get(), selling_price=selling_price, default_cost=default_cost,
                    reorder_level=reorder_level, opening_quantity=opening_quantity,
                )
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        except ValueError:
            self.error_label.config(text="تأكد من إدخال رقم صحيح للكمية.")
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()


class StockAdjustWindow(tk.Toplevel):
    def __init__(self, master, product, on_saved=None, repo=inventory_repo):
        super().__init__(master)
        self.product = product
        self.on_saved = on_saved
        self.repo = repo
        self.title(f"تعديل رصيد: {product.name}")
        self.geometry("340x300")
        self.resizable(False, False)
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text=f"الرصيد الحالي: {self.product.quantity}").pack(**pad)

        self.direction_var = tk.StringVar(value="إضافة")
        ttk.Radiobutton(self, text="إضافة", variable=self.direction_var, value="إضافة").pack(anchor="e", **pad)
        ttk.Radiobutton(self, text="صرف", variable=self.direction_var, value="صرف").pack(anchor="e", **pad)

        self.qty_var = tk.StringVar(value="1")
        ttk.Label(self, text="الكمية").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.qty_var).pack(fill="x", **pad)

        self.reason_var = tk.StringVar()
        ttk.Label(self, text="سبب الحركة").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.reason_var).pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)

        ttk.Button(self, text="تأكيد", command=self._submit).pack(pady=12)

    def _submit(self):
        try:
            qty = int(self.qty_var.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            self.error_label.config(text="أدخل كمية صحيحة أكبر من صفر.")
            return
        delta = qty if self.direction_var.get() == "إضافة" else -qty
        try:
            self.repo.adjust_stock(self.product.id, delta, self.reason_var.get())
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class ProductPickerWindow(tk.Toplevel):
    """Modal picker used from the sales/maintenance flows. Sets
    `self.selected_product` before closing (stays None if the window is
    dismissed). Caller should use `wait_window()`."""

    def __init__(self, master, repo=inventory_repo):
        super().__init__(master)
        self.repo = repo
        self.selected_product = None
        self.title("اختيار صنف")
        self.geometry("420x460")
        self._build()
        self.grab_set()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var)
        entry.pack(fill="x", expand=True, padx=4)
        entry.bind("<KeyRelease>", lambda e: self._reload())
        ttk.Label(self, text="ابحث بالاسم أو SKU أو الباركود").pack(anchor="e", padx=10)

        columns = ("name", "price", "qty")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [("name", "الاسم", 220), ("price", "السعر", 90), ("qty", "المتاح", 90)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._choose_selected())
        ttk.Button(self, text="اختيار", command=self._choose_selected).pack(pady=6)

        self._products = []
        self._reload()

    def _reload(self):
        all_products = self.repo.list_products(query=self.search_var.get())
        self._products = [p for p in all_products if p.active and (p.product_type == "SERVICE" or p.quantity > 0)]
        self.tree.delete(*self.tree.get_children())
        for p in self._products:
            qty_display = "-" if p.product_type == "SERVICE" else p.quantity
            self.tree.insert("", "end", iid=p.id, values=(p.name, f"{p.selling_price:.2f}", qty_display))

    def _choose_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_product = next(p for p in self._products if p.id == selection[0])
        self.destroy()
