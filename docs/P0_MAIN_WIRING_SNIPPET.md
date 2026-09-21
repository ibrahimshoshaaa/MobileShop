# In main.py, use the durable engine's connection and transaction runner for sync storage.
# Replace the existing independent sync protocol construction with:
sync_protocol = SyncProtocol(
    connection=engine.connection,
    transaction=engine.transaction,
)
