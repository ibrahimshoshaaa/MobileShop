import tkinter as tk
from tkinter import messagebox, ttk

import api_access_repo
from errors import AppError

class AccessTab(ttk.Frame):
    def __init__(self, master, repo=api_access_repo):
        super().__init__(master)
        self.repo=repo
        self._build()
        self.reload()

    def _build(self):
        bar=ttk.Frame(self); bar.pack(fill="x",padx=12,pady=8)
        ttk.Button(bar,text="إضافة فرع",command=self._add_branch).pack(side="right",padx=4)
        ttk.Button(bar,text="إضافة دور",command=self._add_role).pack(side="right",padx=4)
        ttk.Button(bar,text="إضافة مستخدم",command=self._add_user).pack(side="right",padx=4)
        ttk.Button(bar,text="تحديث",command=self.reload).pack(side="left",padx=4)

        self.tree=ttk.Treeview(self,columns=("type","name","details","status"),show="headings")
        for col,label,w in [("type","النوع",100),("name","الاسم",220),("details","التفاصيل",420),("status","الحالة",100)]:
            self.tree.heading(col,text=label); self.tree.column(col,width=w,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=12,pady=8)

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        for b in self.repo.list_branches():
            self.tree.insert("", "end", values=("فرع",b.name,b.code,"مفعّل" if b.active else "معطّل"))
        for r in self.repo.list_roles():
            self.tree.insert("", "end", values=("دور",r.name,", ".join(r.permissions) or "بدون صلاحيات","مفعّل" if r.active else "معطّل"))
        for u in self.repo.list_users():
            details=f"ID: {u.id} | الفروع: {', '.join(u.branch_ids) or 'لا يوجد'} | الدور: {u.role_id or 'بدون'} | صلاحيات إضافية: {len(u.permissions)}"
            self.tree.insert("", "end", values=("مستخدم",u.name,details,"مفعّل" if u.active else "معطّل"))

    def _simple_dialog(self,title,fields,on_submit):
        win=tk.Toplevel(self); win.title(title); win.geometry("360x260"); win.grab_set()
        vars={}
        for key,label in fields:
            ttk.Label(win,text=label).pack(anchor="e",padx=12,pady=5)
            v=tk.StringVar(); vars[key]=v; ttk.Entry(win,textvariable=v).pack(fill="x",padx=12)
        err=ttk.Label(win,text="",foreground="red"); err.pack(fill="x",padx=12,pady=5)
        def submit():
            try: on_submit(vars)
            except AppError as e: err.config(text=e.message); return
            win.destroy(); self.reload()
        ttk.Button(win,text="حفظ",command=submit).pack(pady=10)

    def _add_branch(self):
        self._simple_dialog("إضافة فرع",[("name","اسم الفرع"),("code","كود الفرع")],lambda v:self.repo.add_branch(name=v["name"].get(),code=v["code"].get()))

    def _add_role(self):
        self._simple_dialog("إضافة دور",[("name","اسم الدور"),("permissions","الصلاحيات (مفصولة بفواصل)")],lambda v:self.repo.add_role(name=v["name"].get(),permissions=[x.strip() for x in v["permissions"].get().split(",") if x.strip()]))

    def _add_user(self):
        self._simple_dialog("إضافة مستخدم",[("id","معرّف المستخدم (User ID)"),("name","اسم المستخدم"),("branches","أكواد/IDs الفروع مفصولة بفواصل"),("role","Role ID (اختياري)")],
            lambda v:self.repo.add_user(user_id=v["id"].get(),name=v["name"].get(),branch_ids=[x.strip() for x in v["branches"].get().split(",") if x.strip()],role_id=v["role"].get().strip() or None))
