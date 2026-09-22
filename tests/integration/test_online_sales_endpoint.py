from fastapi.testclient import TestClient

from backend.api_server.main import app


def test_sales_read_endpoint_is_available_to_authorized_dev_user():
    client = TestClient(app)

    unauthorized = client.get("/sales")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/sales?branch_id=LOCAL_BRANCH&limit=10",
        headers={"Authorization": "Bearer dev-owner-token"},
    )
    assert authorized.status_code == 200
    body = authorized.json()
    assert body["ok"] is True
    assert isinstance(body["data"], list)
