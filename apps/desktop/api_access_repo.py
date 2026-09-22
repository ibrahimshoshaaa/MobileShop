from __future__ import annotations

import uuid
from dataclasses import dataclass
from api_client import ApiClient
from errors import AppError

@dataclass
class Branch:
    id: str
    name: str
    code: str
    active: bool = True

@dataclass
class ERPUser:
    id: str
    name: str
    branch_ids: tuple[str,...] = ()
    role_id: str|None = None
    permissions: tuple[str,...] = ()
    active: bool = True

@dataclass
class Role:
    id: str
    name: str
    permissions: tuple[str,...] = ()
    active: bool = True

_client = ApiClient()

def list_branches():
    return [Branch(x["id"],x["name"],x["code"],bool(x.get("active",True))) for x in _client.get_entity("branches")]

def list_roles():
    return [Role(x["id"],x["name"],tuple(x.get("permissions",())),bool(x.get("active",True))) for x in _client.get_entity("roles")]

def list_users():
    return [ERPUser(x["id"],x["name"],tuple(x.get("branch_ids",())),x.get("role_id"),tuple(x.get("permissions",())),bool(x.get("active",True))) for x in _client.get_entity("users")]

def add_branch(*,name,code):
    if not name.strip() or not code.strip(): raise AppError("اسم وكود الفرع مطلوبان.")
    return _client.command(f"cmd-branch-{uuid.uuid4().hex[:12]}","createBranch",{"name":name.strip(),"code":code.strip()})

def add_role(*,name,permissions=()):
    if not name.strip(): raise AppError("اسم الدور مطلوب.")
    return _client.command(f"cmd-role-{uuid.uuid4().hex[:12]}","createRole",{"name":name.strip(),"permissions":list(permissions)})

def add_user(*,user_id,name,branch_ids=(),role_id=None,permissions=()):
    if not user_id.strip() or not name.strip(): raise AppError("معرّف المستخدم والاسم مطلوبان.")
    return _client.command(f"cmd-user-{uuid.uuid4().hex[:12]}","createUserProfile",{"id":user_id.strip(),"name":name.strip(),"branch_ids":list(branch_ids),"role_id":role_id,"permissions":list(permissions)})

def update_user_access(*,user_id,branch_ids,role_id=None,permissions=()):
    return _client.command(f"cmd-access-{uuid.uuid4().hex[:12]}","updateUserAccess",{"user_id":user_id,"branch_ids":list(branch_ids),"role_id":role_id,"permissions":list(permissions)})
