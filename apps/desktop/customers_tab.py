"""Customers tab for the desktop POS, plus CustomerPickerWindow used elsewhere."""
import tkinter as tk
from tkinter import messagebox, ttk

import customers_repo
from errors import AppError


class CustomersTab(ttk.Frame):
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
        ttk.Button(bar, text="إضافة عميل", command=self._add).pack(side="left", padx=4)
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
        for c in customers_repo.list_customers(query=self.search_var.get()):
            self.tree.insert("", "end", iid=c.id, values=(c.name, c.phone or "-", "مفعّل" if c.active else "معطّل"))

    def _selected_customer(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("تنبيه", "اختر عميلًا أولًا.")
            return None
        return customers_repo.get_customer(selection[0])

    def _add(self):
        CustomerFormWindow(self, on_saved=self.reload)

    def _edit_selected(self):
        customer = self._selected_customer()
        if customer:
            CustomerFormWindow(self, existing=customer, on_saved=self.reload)


class CustomerFormWindow(tk.Toplevel):
    def __init__(self, master, existing=None, on_saved=None):
        super().__init__(master)
        self.existing = existing
        self.on_saved = on_saved
        self.title("تعديل عميل" if existing else "إضافة عميل جديد")
        self.geometry("340x300")
        self.resizable(False, False)
        self._build()
        self.grab_set()

    def _build(self):
        c = self.existing
        pad = {"padx": 12, "pady": 6}
        self.name_var = tk.StringVar(value=c.name if c else "")
        self.phone_var = tk.StringVar(value=(c.phone or "") if c else "")
        self.active_var = tk.BooleanVar(value=c.active if c else True)

        ttk.Label(self, text="اسم العميل").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.name_var).pack(fill="x", **pad)
        ttk.Label(self, text="رقم الهاتف (اختياري)").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.phone_var).pack(fill="x", **pad)
        if c:
            ttk.Checkbutton(self, text="العميل مفعّل", variable=self.active_var).pack(anchor="e", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="حفظ" if c else "إضافة", command=self._submit).pack(pady=12)

    def _submit(self):
        try:
            if self.existing:
                updated = customers_repo.Customer(
                    id=self.existing.id, name=self.name_var.get().strip(),
                    phone=self.phone_var.get().strip() or None, active=self.active_var.get(),
                )
                customers_repo.update_customer(updated)
            else:
                customers_repo.add_customer(name=self.name_var.get(), phone=self.phone_var.get())
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class CustomerPickerWindow(tk.Toplevel):
    """Modal picker: sets `self.selected_customer` (or leaves it None for a
    walk-in sale) before closing. Caller should use `wait_window()`."""

    def __init__(self, master):
        super().__init__(master)
        self.selected_customer = None
        self.title("اختيار عميل")
        self.geometry("380x420")
        self._build()
        self.grab_set()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var)
        entry.pack(side="right", fill="x", expand=True, padx=4)
        entry.bind("<KeyRelease>", lambda e: self._reload())
        ttk.Button(top, text="عميل جديد", command=self._add_new).pack(side="left", padx=4)

        ttk.Button(self, text="بدون عميل (عميل نقدي)", command=self._choose_none).pack(fill="x", padx=10, pady=4)

        self.listbox = tk.Listbox(self)
        self.listbox.pack(fill="both", expand=True, padx=10, pady=8)
        self.listbox.bind("<Double-1>", lambda e: self._choose_selected())
        ttk.Button(self, text="اختيار", command=self._choose_selected).pack(pady=6)

        self._customers = []
        self._reload()

    def _reload(self):
        self._customers = [c for c in customers_repo.list_customers(query=self.search_var.get()) if c.active]
        self.listbox.delete(0, "end")
        for c in self._customers:
            self.listbox.insert("end", f"{c.name}  {('- ' + c.phone) if c.phone else ''}")

    def _add_new(self):
        form = CustomerFormWindow(self, on_saved=self._reload)
        self.wait_window(form)

    def _choose_none(self):
        self.selected_customer = None
        self.destroy()

    def _choose_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        self.selected_customer = self._customers[selection[0]]
        self.destroy()
