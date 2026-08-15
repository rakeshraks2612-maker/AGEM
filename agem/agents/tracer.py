"""Agent observability tracer backed by Firestore."""
import os
import time
import threading
from typing import List, Dict

os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

try:
    from google.cloud import firestore
    _db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"))
    _FS_OK = True
except Exception:
    _db = None
    _FS_OK = False


class AgentTracer:
    def __init__(self):
        self._mem = []

    def record(self, step: str, detail: str, status: str = "ok") -> None:
        doc = {"timestamp": time.time(), "step": step, "detail": detail, "status": status}
        self._mem.append(doc)
        if _FS_OK and _db:
            def _bg_write():
                try:
                    _db.collection("agem_traces").add(doc, timeout=1.0)
                except Exception:
                    pass
            threading.Thread(target=_bg_write, daemon=True).start()

    def get_traces(self, limit: int = 100) -> List[Dict]:
        if _FS_OK and _db:
            try:
                docs = _db.collection("agem_traces").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream(timeout=1.5)
                res = [d.to_dict() for d in docs]
                if res:
                    return res
            except Exception:
                pass
        return list(reversed(self._mem[-limit:]))