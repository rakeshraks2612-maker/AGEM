"""Human-in-the-loop approval queue."""
import time
from typing import Dict, List

class ApprovalQueue:
    """Manages pending optimization patches awaiting human approval."""
    def __init__(self):
        self._pending = {}

    def add(self, patch_id, patch):
        self._pending[patch_id] = {
            "patch": patch,
            "timestamp": time.time(),
            "status": "pending",
        }

    def list_pending(self):
        return [
            {"patch_id": k, **v}
            for k, v in self._pending.items()
            if v.get("status") == "pending"
        ]

    def approve(self, patch_id):
        if patch_id in self._pending:
            self._pending[patch_id]["status"] = "approved"
            return True
        return False

    def reject(self, patch_id):
        if patch_id in self._pending:
            self._pending[patch_id]["status"] = "rejected"
            return True
        return False
