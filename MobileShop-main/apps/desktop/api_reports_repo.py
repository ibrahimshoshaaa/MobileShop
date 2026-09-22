from datetime import date
from api_client import ApiClient
from errors import AppError

_client = ApiClient()

def get_report(start: date | None = None, end: date | None = None):
    params=[]
    if start: params.append(f"start={start.isoformat()}")
    if end: params.append(f"end={end.isoformat()}")
    query=("?"+"&".join(params)) if params else ""
    result=_client._request("GET",f"/reports{query}")
    if not result.get("ok",True):
        raise AppError((result.get("error") or {}).get("message","تعذّر تحميل التقرير."))
    return result.get("data",{})
