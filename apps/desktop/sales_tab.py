"""Sales tab for the desktop POS — Tkinter port of the mobile sales screens."""
import tkinter as tk
from tkinter import messagebox, ttk

import sales_repo
import inventory_repo
import customers_repo
from customers_tab import CustomerPickerWindow
from errors import AppError
from inventory_tab import ProductPickerWindow


class SalesTab(ttk.Frame):
    def __init__(self, master, repo=sales_repo, inventory_repo_module=inventory_repo, customers_repo_module=customers_repo):
        super().__init__(master)
        self.repo = repo
        self.inventory_repo = inventory_repo_module
        self.customers_repo = customers_repo_module
        self._build()
        self.reload()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=8)
        ttk.Button(bar, text="فاتورة بيع جديدة", command=self._new_sale).pack(side="right", padx=4)
        ttk.Button(bar, text="تحديث", command=self.reload).pack(side="right", padx=4)

        columns = ("id", "items", "total", "time", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col, text, width in [
            ("id", "رقم الفاتورة", 120), ("items", "عدد الأصناف", 90),
            ("total", "الإجمالي", 100), ("time", "الوقت", 150), ("status", "الحالة", 90),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")
        self.tree.tag_configure("voided", foreground="#b00020")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._open_detail())

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        self._sales = {s.id: s for s in self.repo.list_recent_sales()}
        for s in self._sales.values():
            tags = ("voided",) if s.status == "VOIDED" else ()
            self.tree.insert(
                "", "end", iid=s.id,
                values=(s.id[-6:], len(s.items), f"{s.total:.2f}", s.created_at.strftime("%Y-%m-%d %H:%M"),
                        "ملغاة" if s.status == "VOIDED" else "مكتملة"),
                tags=tags,
            )

    def _new_sale(self):
        window = NewSaleWindow(self, repo=self.repo, inventory_repo_module=self.inventory_repo, customers_repo_module=self.customers_repo)
        self.wait_window(window)
        self.reload()

    def _open_detail(self):
        selection = self.tree.selection()
        if not selection:
            return
        sale = self._sales.get(selection[0])
        if sale:
            window = SaleDetailWindow(self, sale)
            self.wait_window(window)
            self.reload()


class NewSaleWindow(tk.Toplevel):
    def __init__(self, master, repo=sales_repo, inventory_repo_module=inventory_repo, customers_repo_module=customers_repo):
        super().__init__(master)
        self.repo = repo
        self.inventory_repo = inventory_repo_module
        self.customers_repo = customers_repo_module
        self.title("فاتورة بيع جديدة")
        self.geometry("640x680")
        self.customer = None
        self.cart = []  # list of self.repo.SaleItem
        self.payments = []  # list of self.repo.Payment
        self._build()
        self.grab_set()

    def _build(self):
        pad = {"padx": 12, "pady": 6}

        customer_bar = ttk.Frame(self)
        customer_bar.pack(fill="x", **pad)
        self.customer_label = ttk.Label(customer_bar, text="بدون عميل (عميل نقدي)")
        self.customer_label.pack(side="right")
        ttk.Button(customer_bar, text="اختيار عميل", command=self._pick_customer).pack(side="left")

        cart_bar = ttk.Frame(self)
        cart_bar.pack(fill="x", **pad)
        ttk.Button(cart_bar, text="إضافة منتج", command=self._add_product).pack(side="right", padx=4)
        ttk.Button(cart_bar, text="حذف من الفاتورة", command=self._remove_selected).pack(side="right", padx=4)
        ttk.Button(cart_bar, text="+1", width=3, command=lambda: self._change_qty(1)).pack(side="left", padx=2)
        ttk.Button(cart_bar, text="-1", width=3, command=lambda: self._change_qty(-1)).pack(side="left", padx=2)

        self.cart_tree = ttk.Treeview(self, columns=("name", "qty", "price", "total"), show="headings", height=8)
        for col, text, width in [("name", "الصنف", 220), ("qty", "الكمية", 70), ("price", "السعر", 90), ("total", "الإجمالي", 90)]:
            self.cart_tree.heading(col, text=text)
            self.cart_tree.column(col, width=width, anchor="center")
        self.cart_tree.pack(fill="both", expand=False, padx=12, pady=4)

        discount_bar = ttk.Frame(self)
        discount_bar.pack(fill="x", **pad)
        ttk.Label(discount_bar, text="الخصم").pack(side="right")
        self.discount_var = tk.StringVar(value="0")
        discount_entry = ttk.Entry(discount_bar, textvariable=self.discount_var, width=10)
        discount_entry.pack(side="right", padx=6)
        discount_entry.bind("<KeyRelease>", lambda e: self._refresh_summary())

        self.summary_label = ttk.Label(self, text="", font=("TkDefaultFont", 11, "bold"))
        self.summary_label.pack(fill="x", padx=12, pady=4)

        payments_bar = ttk.Frame(self)
        payments_bar.pack(fill="x", **pad)
        ttk.Label(payments_bar, text="طرق الدفع", font=("TkDefaultFont", 10, "bold")).pack(side="right")
        ttk.Button(payments_bar, text="إضافة دفعة", command=self._add_payment).pack(side="left", padx=4)
        ttk.Button(payments_bar, text="حذف الدفعة المحددة", command=self._remove_payment).pack(side="left", padx=4)

        self.payments_tree = ttk.Treeview(self, columns=("method", "amount"), show="headings", height=4)
        self.payments_tree.heading("method", text="الطريقة")
        self.payments_tree.heading("amount", text="المبلغ")
        self.payments_tree.pack(fill="x", padx=12, pady=4)

        self.remaining_label = ttk.Label(self, text="")
        self.remaining_label.pack(fill="x", padx=12, pady=4)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)

        ttk.Button(self, text="إتمام البيع", command=self._submit).pack(pady=12)
        self._refresh_summary()

    def _pick_customer(self):
        picker = CustomerPickerWindow(self, repo=self.customers_repo)
        self.wait_window(picker)
        self.customer = picker.selected_customer
        self.customer_label.config(text=self.customer.name if self.customer else "بدون عميل (عميل نقدي)")

    def _add_product(self):
        picker = ProductPickerWindow(self, repo=self.inventory_repo)
        self.wait_window(picker)
        product = picker.selected_product
        if not product:
            return
        for line in self.cart:
            if line.product_id == product.id:
                line.quantity += 1
                self._refresh_cart()
                return
        self.cart.append(sales_repo.SaleItem(product_id=product.id, product_name=product.name, quantity=1, unit_price=product.selling_price))
        self._refresh_cart()

    def _selected_cart_index(self):
        selection = self.cart_tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _change_qty(self, delta):
        idx = self._selected_cart_index()
        if idx is None:
            return
        line = self.cart[idx]
        line.quantity += delta
        if line.quantity <= 0:
            self.cart.pop(idx)
        self._refresh_cart()

    def _remove_selected(self):
        idx = self._selected_cart_index()
        if idx is not None:
            self.cart.pop(idx)
            self._refresh_cart()

    def _refresh_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        for i, line in enumerate(self.cart):
            self.cart_tree.insert("", "end", iid=str(i), values=(line.product_name, line.quantity, f"{line.unit_price:.2f}", f"{line.line_total:.2f}"))
        self._refresh_summary()

    def _subtotal(self):
        return sum(line.line_total for line in self.cart)

    def _discount(self):
        try:
            return float(self.discount_var.get())
        except ValueError:
            return 0.0

    def _total(self):
        return max(self._subtotal() - self._discount(), 0)

    def _paid(self):
        return sum(p.amount for p in self.payments)

    def _refresh_summary(self):
        subtotal = self._subtotal()
        total = self._total()
        self.summary_label.config(text=f"الإجمالي الفرعي: {subtotal:.2f}  |  الإجمالي: {total:.2f} ج.م")
        remaining = total - self._paid()
        if abs(remaining) <= 0.01:
            self.remaining_label.config(text="المدفوع يساوي الإجمالي ✓", foreground="green")
        else:
            self.remaining_label.config(text=f"المتبقي: {remaining:.2f} ج.م", foreground="red")

    def _add_payment(self):
        dialog = PaymentEntryDialog(self, default_amount=self._total() - self._paid())
        self.wait_window(dialog)
        if dialog.result:
            self.payments.append(dialog.result)
            self._refresh_payments()

    def _remove_payment(self):
        selection = self.payments_tree.selection()
        if not selection:
            return
        self.payments.pop(int(selection[0]))
        self._refresh_payments()

    def _refresh_payments(self):
        self.payments_tree.delete(*self.payments_tree.get_children())
        for i, p in enumerate(self.payments):
            self.payments_tree.insert("", "end", iid=str(i), values=(self.repo.PAYMENT_METHOD_LABELS[p.method], f"{p.amount:.2f}"))
        self._refresh_summary()

    def _submit(self):
        try:
            self.repo.create_sale(
                items=self.cart, payments=self.payments,
                customer_id=self.customer.id if self.customer else None,
                customer_name=self.customer.name if self.customer else None,
                discount=self._discount(),
            )
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        messagebox.showinfo("تم", "تم إتمام البيع بنجاح")
        self.destroy()


class PaymentEntryDialog(tk.Toplevel):
    def __init__(self, master, default_amount=0.0):
        super().__init__(master)
        self.result = None
        self.title("إضافة دفعة")
        self.geometry("300x220")
        self._build(default_amount)
        self.grab_set()

    def _build(self, default_amount):
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text="طريقة الدفع").pack(anchor="e", **pad)
        self.method_var = tk.StringVar(value=self.repo.PAYMENT_METHODS[0][1])
        ttk.Combobox(self, textvariable=self.method_var, values=[label for _, label in sales_repo.PAYMENT_METHODS], state="readonly").pack(fill="x", **pad)

        ttk.Label(self, text="المبلغ").pack(anchor="e", **pad)
        self.amount_var = tk.StringVar(value=f"{max(default_amount, 0):.2f}")
        ttk.Entry(self, textvariable=self.amount_var).pack(fill="x", **pad)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12)
        ttk.Button(self, text="إضافة", command=self._submit).pack(pady=10)

    def _submit(self):
        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            self.error_label.config(text="أدخل مبلغًا صحيحًا أكبر من صفر.")
            return
        code = next(code for code, label in sales_repo.PAYMENT_METHODS if label == self.method_var.get())
        self.result = sales_repo.Payment(method=code, amount=amount)
        self.destroy()


class SaleDetailWindow(tk.Toplevel):
    def __init__(self, master, sale):
        super().__init__(master)
        self.sale = sale
        self.title(f"فاتورة #{sale.id[-6:]}")
        self.geometry("420x500")
        self._build()
        self.grab_set()

    def _build(self):
        s = self.sale
        pad = {"padx": 12, "pady": 4}
        if s.status == "VOIDED":
            ttk.Label(self, text="هذه الفاتورة ملغاة", foreground="red").pack(**pad)
        ttk.Label(self, text=f"العميل: {s.customer_name or 'بدون عميل (عميل نقدي)'}").pack(anchor="e", **pad)

        ttk.Label(self, text="الأصناف", font=("TkDefaultFont", 10, "bold")).pack(anchor="e", **pad)
        for item in s.items:
            ttk.Label(self, text=f"{item.product_name}  —  {item.unit_price:.2f} × {item.quantity} = {item.line_total:.2f}").pack(anchor="e", padx=20)

        ttk.Separator(self).pack(fill="x", pady=8)
        ttk.Label(self, text=f"الإجمالي الفرعي: {s.subtotal:.2f} ج.م").pack(anchor="e", **pad)
        ttk.Label(self, text=f"الخصم: {s.discount:.2f} ج.م").pack(anchor="e", **pad)
        ttk.Label(self, text=f"الإجمالي: {s.total:.2f} ج.م", font=("TkDefaultFont", 10, "bold")).pack(anchor="e", **pad)

        ttk.Label(self, text="طرق الدفع", font=("TkDefaultFont", 10, "bold")).pack(anchor="e", **pad)
        for p in s.payments:
            ttk.Label(self, text=f"{sales_repo.PAYMENT_METHOD_LABELS[p.method]}: {p.amount:.2f} ج.م").pack(anchor="e", padx=20)

        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.pack(fill="x", padx=12, pady=6)

        if s.status != "VOIDED":
            ttk.Button(self, text="إلغاء الفاتورة", command=self._void).pack(pady=12)

    def _void(self):
        if not messagebox.askyesno("تأكيد", "هل تريد إلغاء هذه الفاتورة؟ سيتم إرجاع الكميات للمخزون."):
            return
        try:
            self.repo.void_sale(self.sale.id)
        except AppError as e:
            self.error_label.config(text=e.message)
            return
        self.destroy()
