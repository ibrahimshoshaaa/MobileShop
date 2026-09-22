"""Expenses tab for the desktop POS."""
import tkinter as tk
from tkinter import ttk

import expenses_repo
from errors import AppError


class ExpensesTab(ttk.Frame):
    def __init__(self, master, repo=expenses_repo):
        super().__init__(master)
        self.repo = repo
        self._build()
        self.reload()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=8)
        self.total_label = ttk.Label(top, text="", font=("TkDefaultFont", 12, "bold"))
        self.total_label.pack(side="right")
        ttk.Button(top, text="إضافة مصروف", command=self._add).pack(side="left", padx=4)
        ttk.Button(top, text="تحديث", command=self.reload).pack(side="left", padx=4)

        columns = ("category", "amount", "method", "time", "note")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [
            ("category", "التصنيف", 140), ("amount", "المبلغ", 90), ("method", "دُفع من", 90),
            ("time", "الوقت", 150), ("note", "ملاحظة", 200),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        method_labels = dict(self.repo.PAYMENT_METHODS)
        for e in self.repo.list_expenses():
            label = method_labels.get(e.method, e.method)
            self.tree.insert("", "end", iid=e.id, values=(
                e.category, f"{e.amount:.2f}", label, e.created_at.strftime("%Y-%m-%d %H:%M"), e.note or "",
            ))
        total = self.repo.total_for_today()
        self.total_label.config(text=f"إجمالي مصروفات اليوم: {total:.2f} ج.م")

    def _add(self):
        window = ExpenseFormWindow(self, repo=self.repo)
        self.wait_window(window)
        self.reload()


class ExpenseFormWindow(tk.Toplevel):
    def __init__(self, master, repo=expenses_repo):
        super().__init__(master)
        self.repo = repo
        self.title("إضافة مصروف")
        self.geometry("340x400")
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}

        ttk.Label(self, text="التصنيف").pack(anchor="e", **pad)
        self.category_var = tk.StringVar(value=self.repo.EXPENSE_CATEGORIES[0])
        ttk.Combobox(self, textvariable=self.category_var, values=expenses_repo.EXPENSE_CATEGORIES, state="readonly").pack(fill="x", **pad)

        ttk.Label(self, text="المبلغ").pack(anchor="e", **pad)
        self.amount_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.amount_var).pack(fill="x", **pad)

        ttk.Label(self, text="دُفع من").pack(anchor="e", **pad)
        self.method_var = tk.StringVar(value=self.repo.PAYMENT_METHODS[0][1])
        ttk.Combobox(self, textvariable=self.method_var, values=[label for _, label in expenses_repo.PAYMENT_METHODS], state="readonly").pack(fill="x", **pad)

        ttk.Label(self, text="ملاحظة (اختياري)").pack(anchor="e", **pad)
        self.note_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.note_var).pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="إضافة", command=self._submit).pack(pady=12)

    def _submit(self):
        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.error_label.config(text="أدخل مبلغًا صحيحًا أكبر من صفر.")
            return
        code = next(code for code, label in expenses_repo.PAYMENT_METHODS if label == self.method_var.get())
        try:
            self.repo.add_expense(amount=amount, category=self.category_var.get(), method=code, note=self.note_var.get())
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()
