from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from .local_store import LocalStore
from .queue import CommandQueue, QueuedCommand

@dataclass
class SyncResult:
    applied: list
    conflicts: list
    failed: list
    skipped: list = None

class OfflineSync:
    """Offline queue processor with tenant/branch scoping and safe retry semantics."""
    def __init__(self, queue=None, store: LocalStore | None = None, max_attempts: int = 4,
                 base_delay_seconds: float = 0.5, sleep_fn=time.sleep):
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.store = store
        self.queue = queue or CommandQueue()
        self.max_attempts = max_attempts
        self.base_delay_seconds = max(0.0, base_delay_seconds)
        self.sleep_fn = sleep_fn

    def enqueue(self, command_id, payload):
        if not command_id or not isinstance(payload, dict):
            raise ValueError("command_id and object payload are required")
        if self.store:
            self.store.enqueue(command_id, payload)
            return command_id
        return self.queue.enqueue(QueuedCommand(command_id, payload))

    @staticmethod
    def _scope_ok(payload, profile):
        if not profile:
            return True
        tenant = payload.get("_tenant_id")
        branch = payload.get("_branch_id")
        # Scoped envelopes are mandatory when a local account is linked.
        if profile.get("tenant_id") and (tenant != profile["tenant_id"]):
            return False
        if branch and branch not in profile.get("branch_ids", []):
            return False
        return True

    def sync(self, executor):
        result = SyncResult([], [], [], [])
        items = self.store.pending() if self.store else list(self.queue.pending())
        profile = self.store.profile() if self.store else None
        for item in items:
            command_id = item["command_id"] if isinstance(item, dict) else item.command_id
            payload = item["payload"] if isinstance(item, dict) else item.payload
            if self.store and not self._scope_ok(payload, profile):
                self.store.mark(command_id, "CONFLICT", "ACCOUNT_SCOPE_MISMATCH")
                result.conflicts.append(command_id)
                continue
            attempt = 0
            while True:
                try:
                    executor(payload)
                    if self.store: self.store.mark(command_id, "APPLIED")
                    else: item.status = "APPLIED"
                    result.applied.append(command_id)
                    break
                except Exception as exc:
                    code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
                    conflict = code in {"TRANSACTION_CONFLICT", "ACCOUNT_SCOPE_MISMATCH", "STALE_VERSION"}
                    retryable = code in {"TEMPORARY_UNAVAILABLE", "DB_BUSY", "NETWORK_ERROR", "TimeoutError"}
                    attempt += 1
                    if conflict:
                        if self.store: self.store.mark(command_id, "CONFLICT", code)
                        else: item.status = "CONFLICT"
                        result.conflicts.append(command_id)
                        break
                    if retryable and attempt < self.max_attempts:
                        delay = self.base_delay_seconds * (2 ** (attempt - 1))
                        if self.store:
                            when = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
                            self.store.mark_retry(command_id, code, when)
                        self.sleep_fn(delay)
                        continue
                    if self.store: self.store.mark(command_id, "FAILED", code or type(exc).__name__)
                    else: item.status = "FAILED"
                    result.failed.append(command_id)
                    break
        return result
