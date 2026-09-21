"""Installments tab for the desktop POS."""
import tkinter as tk
from tkinter import messagebox, ttk

import installments_repo
import sales_repo
import customers_repo  # for the CASH/WALLET/CARD payment-method labels
from customers_tab import CustomerPickerWindow
from errors import AppError

# Credit doesn't make sense when *collecting* money against an installment
# plan, so it's left out of the picker here (same choice as the mobile app).
COLLECTION_METHODS = [m for m in sales_repo.PAYMENT_METHODS if m[0] != "CREDIT"]


class InstallmentsTab(ttk.Frame):
    def __init__(self, master, repo=installments_repo, customers_repo_module=customers_repo):
        super().__init__(master)
        self.repo = repo
        self.customers_repo_module = customers_repo_module
        self._build()
        self.reload()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=8)
        ttk.Button(bar, text="خطة تقسيط جديدة", command=self._new_plan).pack(side="right", padx=4)
        ttk.Button(bar, text="تحديث", command=self.reload).pack(side="right", padx=4)

        columns = ("customer", "monthly", "total", "term", "remaining")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [
            ("customer", "العميل", 180), ("monthly", "القسط الشهري", 110),
            ("total", "الإجمالي", 100), ("term", "المدة", 70), ("remaining", "المتبقي", 100),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.tag_configure("done", foreground="#0a7d32")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._open_detail())

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        self._plans = {p.id: p for p in self.repo.list_plans()}
        for p in self._plans.values():
            remaining = self.repo.remaining(p.id)
            done = remaining <= 0.01
            self.tree.insert(
                "", "end", iid=p.id,
                values=(p.customer_name, f"{p.monthly_amount:.2f}", f"{p.total_due:.2f}", f"{p.term_months} شهر",
                        "مكتمل" if done else f"{remaining:.2f}"),
                tags=("done",) if done else (),
            )

    def _new_plan(self):
        window = NewInstallmentPlanWindow(self, repo=self.repo, customers_repo_module=self.customers_repo_module)
        self.wait_window(window)
        self.reload()

    def _open_detail(self):
        selection = self.tree.selection()
        if not selection:
            return
        plan = self._plans.get(selection[0])
        if plan:
            window = PlanDetailWindow(self, plan, repo=self.repo)
            self.wait_window(window)
            self.reload()


class NewInstallmentPlanWindow(tk.Toplevel):
    def __init__(self, master, repo=installments_repo, customers_repo_module=customers_repo):
        super().__init__(master)
        self.repo = repo
        self.customers_repo_module = customers_repo_module
        self.customer = None
        self.title("خطة تقسيط جديدة")
        self.geometry("380x560")
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}
        customer_bar = ttk.Frame(self)
        customer_bar.pack(fill="x", **pad)
        self.customer_label = ttk.Label(customer_bar, text="اختر عميل")
        self.customer_label.pack(side="right")
        ttk.Button(customer_bar, text="اختيار عميل", command=self._pick_customer).pack(side="left")

        self.price_var = tk.StringVar()
        self.down_var = tk.StringVar(value="0")
        self.rate_var = tk.StringVar(value="0")
        self.term_var = tk.StringVar(value="6")
        self.sale_id_var = tk.StringVar()

        for label, var in [
            ("رقم الفاتورة المرتبطة", self.sale_id_var),
            ("السعر الإجمالي", self.price_var), ("المقدم", self.down_var),
            ("نسبة الزيادة %", self.rate_var), ("عدد الأشهر", self.term_var),
        ]:
            ttk.Label(self, text=label).pack(anchor="e", **pad)
            entry = ttk.Entry(self, textvariable=var)
            entry.pack(fill="x", **pad)
            entry.bind("<KeyRelease>", lambda e: self._refresh_preview())

        self.preview_label = ttk.Label(self, text="", justify="right")
        self.preview_label.pack(fill="x", padx=12, pady=10)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)

        ttk.Button(self, text="إنشاء الخطة", command=self._submit).pack(pady=12)
        self._refresh_preview()

    def _pick_customer(self):
        picker = CustomerPickerWindow(self, repo=self.customers_repo_module)
        self.wait_window(picker)
        if picker.selected_customer:
            self.customer = picker.selected_customer
            self.customer_label.config(text=self.customer.name)

    def _read_inputs(self):
        return float(self.price_var.get()), float(self.down_var.get()), float(self.rate_var.get()), int(self.term_var.get())

    def _refresh_preview(self):
        try:
            price, down, rate, term = self._read_inputs()
            calc = self.repo.calculate(price=price, down_payment=down, rate_percent=rate, term_months=term)
        except (ValueError, AppError):
            self.preview_label.config(text="أدخل بيانات صحيحة لعرض المعاينة")
            return
        self.preview_label.config(
            text=(
                f"المبلغ الممول: {calc['base_financed']:.2f} ج.م\n"
                f"الزيادة: {calc['increase']:.2f} ج.م\n"
                f"الإجمالي المستحق: {calc['total_due']:.2f} ج.م\n"
                f"القسط الشهري: {calc['monthly_amount']:.2f} ج.م"
            )
        )

    def _submit(self):
        if not self.customer:
            self.error_label.config(text="يجب اختيار عميل لخطة التقسيط.")
            return
        try:
            price, down, rate, term = self._read_inputs()
        except ValueError:
            self.error_label.config(text="تأكد من إدخال كل الحقول بأرقام صحيحة.")
            return
        try:
            self.repo.create_plan(
                customer_id=self.customer.id, customer_name=self.customer.name,
                price=price, down_payment=down, rate_percent=rate, term_months=term,
                sale_id=self.sale_id_var.get().strip() or None,
            )
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()


class PlanDetailWindow(tk.Toplevel):
    def __init__(self, master, plan, repo=installments_repo):
        super().__init__(master)
        self.plan = plan
        self.repo = repo
        self.title(f"خطة تقسيط • {plan.customer_name}")
        self.geometry("420x520")
        self._build()
        self.grab_set()

    def _build(self):
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self._render()

    def _render(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        plan = self.plan
        remaining = self.repo.remaining(plan.id)
        done = remaining <= 0.01
        pad = {"padx": 12, "pady": 4}

        ttk.Label(self.body, text=f"الإجمالي المستحق: {plan.total_due:.2f} ج.م").pack(anchor="e", **pad)
        ttk.Label(self.body, text=f"القسط الشهري: {plan.monthly_amount:.2f} ج.م").pack(anchor="e", **pad)
        ttk.Label(self.body, text=f"المدة: {plan.term_months} شهر").pack(anchor="e", **pad)
        ttk.Separator(self.body).pack(fill="x", pady=6)
        ttk.Label(self.body, text=f"المتبقي: {remaining:.2f} ج.م", font=("TkDefaultFont", 11, "bold")).pack(anchor="e", **pad)

        if done:
            ttk.Label(self.body, text="تم سداد الخطة بالكامل", foreground="green").pack(**pad)
        else:
            ttk.Button(self.body, text="تحصيل قسط", command=self._collect).pack(**pad)

        ttk.Label(self.body, text="سجل التحصيل", font=("TkDefaultFont", 10, "bold")).pack(anchor="e", **pad)
        payments = self.repo.list_payments(plan.id)
        if not payments:
            ttk.Label(self.body, text="لا توجد دفعات محصّلة بعد").pack(anchor="e", padx=20)
        for p in payments:
            label = sales_repo.PAYMENT_METHOD_LABELS.get(p.method, p.method)
            ttk.Label(self.body, text=f"{p.amount:.2f} ج.م • {label} • {p.paid_at.strftime('%Y-%m-%d %H:%M')}").pack(anchor="e", padx=20)

    def _collect(self):
        remaining = self.repo.remaining(self.plan.id)
        dialog = CollectPaymentDialog(self, self.plan, remaining, repo=self.repo)
        self.wait_window(dialog)
        self._render()


class CollectPaymentDialog(tk.Toplevel):
    def __init__(self, master, plan, remaining, repo=installments_repo):
        super().__init__(master)
        self.plan = plan
        self.repo = repo
        self.remaining = remaining
        self.title("تحصيل قسط")
        self.geometry("300x260")
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text=f"المتبقي: {self.remaining:.2f} ج.م").pack(**pad)

        default_amount = min(self.plan.monthly_amount, self.remaining)
        self.amount_var = tk.StringVar(value=f"{default_amount:.2f}")
        ttk.Label(self, text="المبلغ").pack(anchor="e", **pad)
        ttk.Entry(self, textvariable=self.amount_var).pack(fill="x", **pad)

        ttk.Label(self, text="طريقة الدفع").pack(anchor="e", **pad)
        self.method_var = tk.StringVar(value=COLLECTION_METHODS[0][1])
        ttk.Combobox(self, textvariable=self.method_var, values=[label for _, label in COLLECTION_METHODS], state="readonly").pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="تأكيد", command=self._submit).pack(pady=10)

    def _submit(self):
        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.error_label.config(text="أدخل مبلغًا صحيحًا أكبر من صفر.")
            return
        code = next(code for code, label in COLLECTION_METHODS if label == self.method_var.get())
        try:
            self.repo.collect_payment(plan_id=self.plan.id, amount=amount, method=code)
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()
