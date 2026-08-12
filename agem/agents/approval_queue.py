"""Human-in-the-loop approval queue backed by Firestore."""
import os
import time
from typing import List, Dict, Optional

try:
    from google.cloud import firestore
    _db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"))
    _FS_OK = True
except Exception:
    _db = None
    _FS_OK = False


class ApprovalQueue:
    def __init__(self):
        self._mem = {}

    def add(self, patch: dict) -> str:
        patch_id = patch.get("id") or ("patch-" + patch.get("resource_id", "unknown") + "-" + str(int(time.time())))
        doc = {
            "id": patch_id,
            "resource_id": patch.get("resource_id", ""),
            "resource_name": patch.get("resource_name", ""),
            "title": patch.get("title", ""),
            "savings": patch.get("savings", 0.0),
            "diff": patch.get("diff", {}),
            "status": "pending",
            "timestamp": time.time(),
            "dry_run": patch.get("dry_run", True),
        }
        self._mem[patch_id] = doc
        if _FS_OK:
            try:
                _db.collection("agem_approvals").document(patch_id).set(doc)
            except Exception as e:
                print("[Queue] Firestore write failed: " + str(e))
        return patch_id

    def list_pending(self) -> List[dict]:
        if _FS_OK:
            try:
                docs = _db.collection("agem_approvals").where("status", "==", "pending").stream()
                return [d.to_dict() for d in docs]
            except Exception as e:
                print("[Queue] Firestore read failed: " + str(e))
        return [v for v in self._mem.values() if v.get("status") == "pending"]

    def list_all(self) -> List[dict]:
        if _FS_OK:
            try:
                docs = _db.collection("agem_approvals").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
                return [d.to_dict() for d in docs]
            except Exception:
                pass
        return sorted(self._mem.values(), key=lambda x: x.get("timestamp", 0), reverse=True)

    def get(self, patch_id: str) -> Optional[dict]:
        if _FS_OK:
            try:
                d = _db.collection("agem_approvals").document(patch_id).get()
                if d.exists:
                    return d.to_dict()
            except Exception:
                pass
        return self._mem.get(patch_id)

    def approve(self, patch_id: str) -> bool:
        if _FS_OK:
            try:
                _db.collection("agem_approvals").document(patch_id).update({"status": "approved"})
            except Exception:
                pass
        if patch_id in self._mem:
            self._mem[patch_id]["status"] = "approved"
            return True
        return False

    def reject(self, patch_id: str) -> bool:
        if _FS_OK:
            try:
                _db.collection("agem_approvals").document(patch_id).update({"status": "rejected"})
            except Exception:
                pass
        if patch_id in self._mem:
            self._mem[patch_id]["status"] = "rejected"
            return True
        return False
