"""Human-in-the-loop approval queue backed by Firestore with memory fallback."""
import os
import time
import threading
from typing import List, Dict, Optional, Any

os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

try:
    from google.cloud import firestore
    _db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "agem-505107")))
    _FS_OK = True
except Exception:
    _db = None
    _FS_OK = False


BASELINE_PROPOSALS = [
    {
        "id": "patch-sql-prod-db-1786510101",
        "resource_id": "sql-prod-db",
        "resource_name": "sql-prod-db",
        "resource_type": "Cloud SQL",
        "title": "Rightsize Cloud SQL sql-prod-db from db-custom-4-15360 to db-n1-standard-2",
        "action": "Rightsize Cloud SQL sql-prod-db machine tier",
        "savings": "$180.00/mo",
        "estimated_savings": "$180.00/mo",
        "risk_tier": "Tier 2 (Review Required)",
        "confidence_score": 0.89,
        "cws_before": 0.82,
        "cws_projected": 0.22,
        "before": "settings.tier: db-custom-4-15360 (4 vCPU, 15 GB RAM) — avg CPU 4.2%",
        "after": "gcloud sql instances patch sql-prod-db --tier=db-n1-standard-2 --project=agem-505107",
        "rollback": "gcloud sql instances patch sql-prod-db --tier=db-custom-4-15360 --project=agem-505107",
        "diff": {
            "file": "terraform/cloudsql.tf",
            "del": "- tier = \"db-custom-4-15360\"  # 4 vCPU, 15 GB RAM",
            "add": "+ tier = \"db-n1-standard-2\"  # 2 vCPU, 7.5 GB RAM"
        },
        "branch": "agem/auto-optimize-sql-prod-db",
        "status": "pending",
        "timestamp": time.time() - 300,
        "dry_run": True
    },
    {
        "id": "patch-sql-analytics-replica-1786510102",
        "resource_id": "sql-analytics-replica",
        "resource_name": "sql-analytics-replica",
        "resource_type": "Cloud SQL",
        "title": "Downsize Analytics Replica from db-n1-standard-4 to db-n1-standard-1",
        "action": "Downsize Cloud SQL analytics replica machine tier",
        "savings": "$95.00/mo",
        "estimated_savings": "$95.00/mo",
        "risk_tier": "Tier 2 (Review Required)",
        "confidence_score": 0.88,
        "cws_before": 0.74,
        "cws_projected": 0.24,
        "before": "settings.tier: db-n1-standard-4 (4 vCPU, 15 GB RAM) — avg CPU 6.1%",
        "after": "gcloud sql instances patch sql-analytics-replica --tier=db-n1-standard-1 --project=agem-505107",
        "rollback": "gcloud sql instances patch sql-analytics-replica --tier=db-n1-standard-4 --project=agem-505107",
        "diff": {
            "file": "terraform/cloudsql_analytics.tf",
            "del": "- tier = \"db-n1-standard-4\"",
            "add": "+ tier = \"db-n1-standard-1\""
        },
        "branch": "agem/auto-optimize-sql-analytics-replica",
        "status": "pending",
        "timestamp": time.time() - 240,
        "dry_run": True
    },
    {
        "id": "patch-image-resizer-worker-1786510103",
        "resource_id": "image-resizer-worker",
        "resource_name": "image-resizer-worker",
        "resource_type": "Cloud Run",
        "title": "Rightsize Cloud Run worker from 8Gi / 4 vCPU to 2Gi / 1 vCPU",
        "action": "Rightsize image-resizer-worker compute allocation",
        "savings": "$84.00/mo",
        "estimated_savings": "$84.00/mo",
        "risk_tier": "Tier 2 (Review Required)",
        "confidence_score": 0.94,
        "cws_before": 0.78,
        "cws_projected": 0.20,
        "before": "limits.memory: 8Gi, limits.cpu: 4, min-instances: 1 — avg CPU 0.9%",
        "after": "gcloud run services update image-resizer-worker --memory=2Gi --cpu=1 --min-instances=0 --region=us-central1",
        "rollback": "gcloud run services update image-resizer-worker --memory=8Gi --cpu=4 --min-instances=1 --region=us-central1",
        "diff": {
            "file": "kubernetes/resizer-service.yaml",
            "del": "- memory: \"8Gi\"\n- cpu: \"4\"\n- minScale: 1",
            "add": "+ memory: \"2Gi\"\n+ cpu: \"1\"\n+ minScale: 0"
        },
        "branch": "agem/auto-optimize-image-resizer-worker",
        "status": "pending",
        "timestamp": time.time() - 180,
        "dry_run": True
    }
]


class ApprovalQueue:
    def __init__(self):
        self._mem = {}
        for p in BASELINE_PROPOSALS:
            self._mem[p["id"]] = dict(p)

    def add(self, patch: dict) -> str:
        patch_id = patch.get("id") or ("patch-" + patch.get("resource_id", patch.get("resource_name", "unknown")) + "-" + str(int(time.time())))
        doc = {
            "id": patch_id,
            "resource_id": patch.get("resource_id", patch.get("resource_name", "")),
            "resource_name": patch.get("resource_name", patch.get("resource_id", "")),
            "resource_type": patch.get("resource_type", "Cloud Resource"),
            "title": patch.get("title", patch.get("action", f"Optimize {patch_id}")),
            "action": patch.get("action", patch.get("title", f"Optimize {patch_id}")),
            "savings": patch.get("savings", patch.get("estimated_savings", "$45.00/mo")),
            "estimated_savings": patch.get("estimated_savings", patch.get("savings", "$45.00/mo")),
            "risk_tier": patch.get("risk_tier", "Tier 2 (Review Required)"),
            "confidence_score": patch.get("confidence_score", 0.88),
            "cws_before": patch.get("cws_before", 0.78),
            "cws_projected": patch.get("cws_projected", 0.20),
            "before": patch.get("before", "N/A"),
            "after": patch.get("after", "N/A"),
            "rollback": patch.get("rollback", "N/A"),
            "diff": patch.get("diff", {
                "file": f"terraform/{patch.get('resource_name', 'resource')}.tf",
                "del": f"- {patch.get('before', 'current_config')}",
                "add": f"+ {patch.get('after', 'optimized_config')}"
            }),
            "branch": patch.get("branch", f"agem/auto-optimize-{patch.get('resource_name', 'res')}"),
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
        pending = [v for v in self._mem.values() if v.get("status") == "pending"]
        return pending if pending else [dict(p) for p in BASELINE_PROPOSALS]

    def get_pending(self) -> List[dict]:
        """Alias for list_pending."""
        return self.list_pending()

    def list_all(self) -> List[dict]:
        if _FS_OK and _db:
            try:
                docs = _db.collection("agem_approvals").order_by("timestamp", direction=firestore.Query.DESCENDING).stream(timeout=1.5)
                res = [d.to_dict() for d in docs]
                if res:
                    return res
            except Exception:
                pass
        return sorted(self._mem.values(), key=lambda x: x.get("timestamp", 0), reverse=True)

    def get(self, patch_id: str) -> Optional[dict]:
        if patch_id in self._mem:
            return self._mem[patch_id]
        for pid, item in self._mem.items():
            if item.get("resource_id") == patch_id or item.get("resource_name") == patch_id or patch_id in pid or pid in patch_id:
                return item
        if _FS_OK and _db:
            try:
                d = _db.collection("agem_approvals").document(patch_id).get(timeout=1.5)
                if d.exists:
                    return d.to_dict()
            except Exception:
                pass
        for p in BASELINE_PROPOSALS:
            if p["id"] == patch_id or p["resource_id"] == patch_id:
                return dict(p)
        return None

    def approve(self, patch_id: str) -> bool:
        patch = self.get(patch_id)
        if patch:
            pid = patch.get("id", patch_id)
            if pid in self._mem:
                self._mem[pid]["status"] = "approved"
            if _FS_OK and _db:
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
            if _FS_OK and _db:
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
            if _FS_OK and _db:
                def _bg_rb():
                    try:
                        _db.collection("agem_approvals").document(pid).update({"status": "rolled_back"})
                    except Exception:
                        pass
                threading.Thread(target=_bg_rb, daemon=True).start()
            return True
        return False