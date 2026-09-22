"""Maintenance tab for the desktop POS."""
import tkinter as tk
from tkinter import messagebox, ttk

import maintenance_repo
import sales_repo
import customers_repo
import inventory_repo  # for PAYMENT_METHODS labels on delivery
from customers_tab import CustomerPickerWindow
from errors import AppError
from inventory_tab import ProductPickerWindow


class MaintenanceTab(ttk.Frame):
    def __init__(self, master, repo=maintenance_repo, customers_repo_module=customers_repo, inventory_repo_module=inventory_repo):
        super().__init__(master)
        self.repo = repo
        self.customers_repo_module = customers_repo_module
        self.inventory_repo_module = inventory_repo_module
        self._build()
        self.reload()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=8)
        ttk.Button(bar, text="طلب صيانة جديد", command=self._new_ticket).pack(side="right", padx=4)
        ttk.Button(bar, text="تحديث", command=self.reload).pack(side="right", padx=4)

        columns = ("device", "customer", "problem", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [
            ("device", "الجهاز", 150), ("customer", "العميل", 150),
            ("problem", "المشكلة", 220), ("status", "الحالة", 130),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.tag_configure("delivered", foreground="#0a7d32")
        self.tree.tag_configure("cancelled", foreground="#b00020")
        self.tree.tag_configure("ready", foreground="#1565c0")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._open_detail())

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        self._tickets = {t.id: t for t in self.repo.list_tickets()}
        for t in self._tickets.values():
            tag = {"DELIVERED": "delivered", "CANCELLED": "cancelled", "READY": "ready"}.get(t.status, "")
            self.tree.insert("", "end", iid=t.id, values=(t.device, t.customer_name, t.problem, t.status_label),
                              tags=(tag,) if tag else ())

    def _new_ticket(self):
        window = NewTicketWindow(self, repo=self.repo, customers_repo_module=self.customers_repo_module)
        self.wait_window(window)
        self.reload()

    def _open_detail(self):
        selection = self.tree.selection()
        if not selection:
            return
        ticket = self._tickets.get(selection[0])
        if ticket:
            window = TicketDetailWindow(self, ticket.id, repo=self.repo, inventory_repo_module=self.inventory_repo_module)
            self.wait_window(window)
            self.reload()


class NewTicketWindow(tk.Toplevel):
    def __init__(self, master, repo=maintenance_repo, customers_repo_module=customers_repo):
        super().__init__(master)
        self.repo = repo
        self.customers_repo_module = customers_repo_module
        self.customer = None
        self.title("طلب صيانة جديد")
        self.geometry("380x460")
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}
        customer_bar = ttk.Frame(self)
        customer_bar.pack(fill="x", **pad)
        self.customer_label = ttk.Label(customer_bar, text="اختر عميل")
        self.customer_label.pack(side="right")
        ttk.Button(customer_bar, text="اختيار عميل", command=self._pick_customer).pack(side="left")

        ttk.Label(self, text="الجهاز (مثال: iPhone 12)").pack(anchor="e", **pad)
        self.device_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.device_var).pack(fill="x", **pad)

        ttk.Label(self, text="IMEI (اختياري)").pack(anchor="e", **pad)
        self.imei_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.imei_var).pack(fill="x", **pad)

        ttk.Label(self, text="وصف المشكلة").pack(anchor="e", **pad)
        self.problem_text = tk.Text(self, height=4)
        self.problem_text.pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="إنشاء الطلب", command=self._submit).pack(pady=12)

    def _pick_customer(self):
        picker = CustomerPickerWindow(self, repo=self.customers_repo_module)
        self.wait_window(picker)
        if picker.selected_customer:
            self.customer = picker.selected_customer
            self.customer_label.config(text=self.customer.name)

    def _submit(self):
        if not self.customer:
            self.error_label.config(text="يجب اختيار عميل.")
            return
        try:
            self.repo.create_ticket(
                customer_id=self.customer.id, customer_name=self.customer.name,
                device=self.device_var.get(), problem=self.problem_text.get("1.0", "end").strip(),
                imei=self.imei_var.get(),
            )
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()


class TicketDetailWindow(tk.Toplevel):
    def __init__(self, master, ticket_id, repo=maintenance_repo, inventory_repo_module=inventory_repo):
        super().__init__(master)
        self.ticket_id = ticket_id
        self.repo = repo
        self.inventory_repo_module = inventory_repo_module
        self.title("تفاصيل طلب الصيانة")
        self.geometry("460x560")
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self._render()
        self.grab_set()

    def _render(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        ticket = next(t for t in self.repo.list_tickets() if t.id == self.ticket_id)
        self.ticket = ticket
        pad = {"padx": 12, "pady": 4}

        ttk.Label(self.body, text=f"الجهاز: {ticket.device}").pack(anchor="e", **pad)
        ttk.Label(self.body, text=f"العميل: {ticket.customer_name}").pack(anchor="e", **pad)
        ttk.Label(self.body, text=f"المشكلة: {ticket.problem}").pack(anchor="e", **pad)
        if ticket.imei:
            ttk.Label(self.body, text=f"IMEI: {ticket.imei}").pack(anchor="e", **pad)
        ttk.Separator(self.body).pack(fill="x", pady=6)

        status_bar = ttk.Frame(self.body)
        status_bar.pack(fill="x", **pad)
        ttk.Label(status_bar, text=f"الحالة: {ticket.status_label}", font=("TkDefaultFont", 10, "bold")).pack(side="right")
        if ticket.is_open and ticket.next_status:
            next_label = self.repo.STATUS_LABELS[ticket.next_status]
            ttk.Button(status_bar, text=f"التالي: {next_label}", command=self._advance).pack(side="left")

        if ticket.is_open:
            ttk.Button(self.body, text="إلغاء الطلب", command=self._cancel).pack(**pad)

        ttk.Separator(self.body).pack(fill="x", pady=6)
        parts_bar = ttk.Frame(self.body)
        parts_bar.pack(fill="x", **pad)
        ttk.Label(parts_bar, text="القطع المستخدمة", font=("TkDefaultFont", 10, "bold")).pack(side="right")
        if ticket.is_open:
            ttk.Button(parts_bar, text="إضافة قطعة", command=self._add_part).pack(side="left")

        parts = self.repo.list_parts_used(ticket.id)
        if not parts:
            ttk.Label(self.body, text="لا توجد قطع مستخدمة بعد").pack(anchor="e", padx=20)
        for p in parts:
            ttk.Label(self.body, text=f"{p.product_name} — {p.cost:.2f} × {p.quantity} = {p.total:.2f}").pack(anchor="e", padx=20)

        ttk.Label(self.body, text=f"إجمالي تكلفة القطع: {ticket.parts_cost:.2f} ج.م",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="e", **pad)

        if ticket.status == "DELIVERED":
            ttk.Separator(self.body).pack(fill="x", pady=6)
            ttk.Label(self.body, text=f"السعر النهائي: {ticket.final_cost:.2f} ج.م").pack(anchor="e", **pad)
            ttk.Label(self.body, text=f"المدفوع: {ticket.payment:.2f} ج.م").pack(anchor="e", **pad)

        if ticket.status == "READY":
            ttk.Button(self.body, text="تسليم الجهاز", command=self._deliver).pack(pady=12)

    def _advance(self):
        try:
            self.repo.advance_status(self.ticket_id)
        except AppError as e:
            messagebox.showerror("خطأ", e.message)
        self._render()

    def _cancel(self):
        if not messagebox.askyesno("تأكيد", "هل تريد إلغاء طلب الصيانة هذا؟"):
            return
        try:
            self.repo.cancel_ticket(self.ticket_id)
        except AppError as e:
            messagebox.showerror("خطأ", e.message)
        self._render()

    def _add_part(self):
        picker = ProductPickerWindow(self, repo=self.inventory_repo_module)
        self.wait_window(picker)
        product = picker.selected_product
        if not product:
            return
        quantity = _ask_quantity(self)
        if not quantity:
            return
        try:
            self.repo.use_part(
                ticket_id=self.ticket_id, product_id=product.id, product_name=product.name,
                quantity=quantity, cost=product.default_cost,
            )
        except AppError as e:
            messagebox.showerror("خطأ", e.message)
        self._render()

    def _deliver(self):
        dialog = DeliverDialog(self, self.ticket, repo=self.repo)
        self.wait_window(dialog)
        self._render()


def _ask_quantity(parent):
    result = {"value": None}
    dialog = tk.Toplevel(parent)
    dialog.title("الكمية المستخدمة")
    dialog.geometry("260x140")
    dialog.grab_set()
    var = tk.StringVar(value="1")
    ttk.Label(dialog, text="الكمية").pack(pady=6)
    ttk.Entry(dialog, textvariable=var).pack(pady=6, padx=12, fill="x")

    def confirm():
        try:
            qty = int(var.get())
            if qty > 0:
                result["value"] = qty
        except ValueError:
            pass
        dialog.destroy()

    ttk.Button(dialog, text="تأكيد", command=confirm).pack(pady=10)
    parent.wait_window(dialog)
    return result["value"]


class DeliverDialog(tk.Toplevel):
    def __init__(self, master, ticket, repo=maintenance_repo):
        super().__init__(master)
        self.ticket = ticket
        self.repo = repo
        self.title("تسليم الجهاز")
        self.geometry("320x320")
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text=f"تكلفة القطع المستخدمة: {self.ticket.parts_cost:.2f} ج.م").pack(**pad)

        ttk.Label(self, text="السعر النهائي").pack(anchor="e", **pad)
        self.price_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.price_var).pack(fill="x", **pad)

        ttk.Label(self, text="المبلغ المدفوع الآن").pack(anchor="e", **pad)
        self.payment_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.payment_var).pack(fill="x", **pad)

        ttk.Label(self, text="طريقة الدفع").pack(anchor="e", **pad)
        self.method_var = tk.StringVar(value=sales_repo.PAYMENT_METHODS[0][1])
        ttk.Combobox(self, textvariable=self.method_var, values=[label for _, label in sales_repo.PAYMENT_METHODS], state="readonly").pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="تأكيد التسليم", command=self._submit).pack(pady=10)

    def _submit(self):
        try:
            price = float(self.price_var.get())
            payment = float(self.payment_var.get())
        except ValueError:
            self.error_label.config(text="أدخل أرقامًا صحيحة.")
            return
        code = next(code for code, label in sales_repo.PAYMENT_METHODS if label == self.method_var.get())
        try:
            self.repo.deliver_ticket(ticket_id=self.ticket.id, final_price=price, payment=payment, method=code)
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()
