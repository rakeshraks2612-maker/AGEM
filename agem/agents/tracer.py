"""Agent observability tracer backed by Firestore."""
import os
import time
from typing import List, Dict

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
        if _FS_OK:
            try:
                _db.collection("agem_traces").add(doc)
            except Exception as e:
                print("[Tracer] Firestore write failed: " + str(e))

    def get_traces(self, limit: int = 100) -> List[Dict]:
        if _FS_OK:
            try:
                docs = _db.collection("agem_traces").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
                return [d.to_dict() for d in docs]
            except Exception as e:
                print("[Tracer] Firestore read failed: " + str(e))
        return list(reversed(self._mem[-limit:]))
