import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import pytest
from backend.functions.repositories.generic import set_tenant_scope, reset_tenant_scope

@pytest.fixture(autouse=True)
def reset_repository_tenant_scope():
    token = set_tenant_scope(None)
    yield
    reset_tenant_scope(token)
