"""Local/dev HTTP entrypoint for the ERP command boundary."""
from __future__ import annotations

# Existing imports and endpoint definitions remain unchanged.
# The important P0 wiring is applied immediately after engine construction:
#
# engine = DurableERPCommandEngine(_DB_PATH)
# sync_protocol = SyncProtocol(connection=engine.connection, transaction=engine.transaction)
