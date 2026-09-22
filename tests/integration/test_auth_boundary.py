from backend.functions.api.http import handle
from shared.contracts.errors import DomainError


class Request:
    def __init__(self, body):
        self.body = body
        self.headers = {}

    def get_json(self, silent=True):
        return self.body


def test_http_rejects_missing_tenant_claim():
    request = Request({"commandId": "c1", "command": "createSale", "branchId": "b1", "payload": {}})
    try:
        handle(request, object(), lambda _: {"uid": "u1", "branch_ids": ["b1"], "permissions": []})
    except DomainError as exc:
        assert exc.code == "TENANT_REQUIRED"
    else:
        raise AssertionError("missing tenant must be rejected")


def test_http_rejects_identity_fields_from_body():
    request = Request({
        "commandId": "c1", "command": "createSale", "branchId": "b1",
        "tenant_id": "attacker", "payload": {},
    })
    try:
        handle(request, object(), lambda _: {
            "uid": "u1", "tenant_id": "t1", "branch_ids": ["b1"], "permissions": [],
        })
    except DomainError as exc:
        assert exc.code == "INVALID_INPUT"
    else:
        raise AssertionError("identity override must be rejected")
