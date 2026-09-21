import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

import api_reports_repo
from errors import AppError

class ReportsTab(ttk.Frame):
    def __init__(self, master, repo=api_reports_repo):
        super().__init__(master)
        self.repo=repo
        self._build()
        self.reload()

    def _build(self):
        bar=ttk.Frame(self); bar.pack(fill="x",padx=12,pady=8)
        ttk.Label(bar,text="من").pack(side="right",padx=4)
        self.start_var=tk.StringVar(value=date.today().replace(day=1).isoformat())
        ttk.Entry(bar,textvariable=self.start_var,width=12).pack(side="right")
        ttk.Label(bar,text="إلى").pack(side="right",padx=4)
        self.end_var=tk.StringVar(value=date.today().isoformat())
        ttk.Entry(bar,textvariable=self.end_var,width=12).pack(side="right")
        ttk.Button(bar,text="تحديث",command=self.reload).pack(side="left",padx=4)

        self.summary=ttk.Label(self,text="",justify="right",font=("TkDefaultFont",11,"bold"))
        self.summary.pack(fill="x",padx=12,pady=10)
        columns=("name","value")
        self.tree=ttk.Treeview(self,columns=columns,show="headings")
        self.tree.heading("name",text="المؤشر"); self.tree.heading("value",text="القيمة")
        self.tree.column("name",width=280,anchor="e"); self.tree.column("value",width=180,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=12,pady=8)

    def reload(self):
        try:
            start=date.fromisoformat(self.start_var.get().strip())
            end=date.fromisoformat(self.end_var.get().strip())
            if end < start: raise ValueError
            data=self.repo.get_report(start,end)
        except (ValueError,AppError) as exc:
            self.summary.config(text=f"تعذّر تحميل التقرير: {getattr(exc,'message',str(exc))}")
            return
        self.tree.delete(*self.tree.get_children())
        items=[
            ("عدد المبيعات",data.get("sales_count",0)),
            ("الإيرادات",f"{data.get('revenue',0)} ج.م"),
            ("تكلفة البضاعة",f"{data.get('cogs',0)} ج.م"),
            ("مجمل الربح",f"{data.get('gross_profit',0)} ج.م"),
            ("إيرادات الصيانة",f"{data.get('maintenance_revenue',0)} ج.م"),
            ("تكلفة الصيانة",f"{data.get('maintenance_cost',0)} ج.م"),
            ("ربح الصيانة",f"{data.get('maintenance_profit',0)} ج.م"),
            ("عمولات التحويل",f"{data.get('transfer_commission',0)} ج.م"),
            ("المصروفات",f"{data.get('expenses',0)} ج.م"),
            ("صافي الربح",f"{data.get('net_profit',0)} ج.م"),
            ("أقساط متأخرة",data.get("overdue_installments",0)),
        ]
        for name,value in items: self.tree.insert("", "end", values=(name,value))
        self.summary.config(text=f"تقرير من {start.isoformat()} إلى {end.isoformat()}")
