"""Suppliers tab for the desktop POS."""
import tkinter as tk
from tkinter import messagebox, ttk

import suppliers_repo
from errors import AppError


class SuppliersTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
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
        ttk.Button(bar, text="إضافة مورد", command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="تعديل", command=self._edit_selected).pack(side="left", padx=4)

        columns = ("name", "phone", "active")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [("name", "الاسم", 220), ("phone", "رقم الهاتف", 160), ("active", "الحالة", 100)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        for s in suppliers_repo.list_suppliers(query=self.search_var.get()):
            self.tree.insert("", "end", iid=s.id, values=(s.name, s.phone or "-", "مفعّل" if s.active else "معطّل"))

    def _selected_supplier(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("تنبيه", "اختر موردًا أولًا.")
            return None
        suppliers = {s.id: s for s in suppliers_repo.list_suppliers()}
        return suppliers.get(selection[0])

    def _add(self):
        SupplierFormWindow(self, on_saved=self.reload)

    def _edit_selected(self):
        supplier = self._selected_supplier()
        if supplier:
            SupplierFormWindow(self, existing=supplier, on_saved=self.reload)


class SupplierFormWindow(tk.Toplevel):
    def __init__(self, master, existing=None, on_saved=None):
        super().__init__(master)
        self.existing = existing
        self.on_saved = on_saved
        self.title("تعديل مورد" if existing else "إضافة مورد جديد")
        self.geometry("340x300")
        self.resizable(False, False)
        self._build()
        self.grab_set()

    def _build(self):
        s = self.existing
        pad = {"padx": 12, "pady": 6}
        self.name_var = tk.StringVar(value=s.name if s else "")
        self.phone_var = tk.StringVar(value=(s.phone or "") if s else "")
        self.active_var = tk.BooleanVar(value=s.active if s else True)

        ttk.Label(self, text="اسم المورد").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.name_var).pack(fill="x", **pad)
        ttk.Label(self, text="رقم الهاتف (اختياري)").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.phone_var).pack(fill="x", **pad)
        if s:
            ttk.Checkbutton(self, text="المورد مفعّل", variable=self.active_var).pack(anchor="e", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="حفظ" if s else "إضافة", command=self._submit).pack(pady=12)

    def _submit(self):
        try:
            if self.existing:
                updated = suppliers_repo.Supplier(
                    id=self.existing.id, name=self.name_var.get().strip(),
                    phone=self.phone_var.get().strip() or None, active=self.active_var.get(),
                )
                suppliers_repo.update_supplier(updated)
            else:
                suppliers_repo.add_supplier(name=self.name_var.get(), phone=self.phone_var.get())
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
