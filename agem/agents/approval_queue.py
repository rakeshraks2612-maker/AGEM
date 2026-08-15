"""Human-in-the-loop approval queue backed by Firestore."""
import os
import time
import threading
from typing import List, Dict, Optional

os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

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
        if _FS_OK and _db:
            def _bg_add():
                try:
                    _db.collection("agem_approvals").document(patch_id).set(doc, timeout=1.0)
                except Exception:
                    pass
            threading.Thread(target=_bg_add, daemon=True).start()
        return patch_id

    def list_pending(self) -> List[dict]:
        try:
            if _FS_OK and _db:
                docs = _db.collection("agem_approvals").where("status", "==", "pending").stream(timeout=1.5)
                res = [d.to_dict() for d in docs]
                if res:
                    return res
        except Exception:
            pass
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
        if patch_id in self._mem:
            return self._mem[patch_id]
        for pid, item in self._mem.items():
            if item.get("resource_id") == patch_id or patch_id in pid or pid in patch_id:
                return item
        if _FS_OK:
            try:
                d = _db.collection("agem_approvals").document(patch_id).get()
                if d.exists:
                    return d.to_dict()
            except Exception:
                pass
        return None

    def approve(self, patch_id: str) -> bool:
        patch = self.get(patch_id)
        if patch:
            pid = patch.get("id", patch_id)
            if pid in self._mem:
                self._mem[pid]["status"] = "approved"
            if _FS_OK:
                def _bg_app():
                    try:
                        _db.collection("agem_approvals").document(pid).update({"status": "approved"})
                    except Exception:
                        pass
                threading.Thread(target=_bg_app, daemon=True).start()
            return True
        return False

    def reject(self, patch_id: str) -> bool:
        patch = self.get(patch_id)
        if patch:
            pid = patch.get("id", patch_id)
            if pid in self._mem:
                self._mem[pid]["status"] = "rejected"
            if _FS_OK:
                def _bg_rej():
                    try:
                        _db.collection("agem_approvals").document(pid).update({"status": "rejected"})
                    except Exception:
                        pass
                threading.Thread(target=_bg_rej, daemon=True).start()
            return True
        return False

    def rollback(self, patch_id: str) -> bool:
        patch = self.get(patch_id)
        if patch:
            pid = patch.get("id", patch_id)
            if pid in self._mem:
                self._mem[pid]["status"] = "rolled_back"
            if _FS_OK:
                def _bg_rb():
                    try:
                        _db.collection("agem_approvals").document(pid).update({"status": "rolled_back"})
                    except Exception:
                        pass
                threading.Thread(target=_bg_rb, daemon=True).start()
            return True
        return False