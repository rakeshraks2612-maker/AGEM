"""Human-in-the-Loop Approval Queue backed by Firestore."""
import os
import time
import uuid
from typing import Dict, List, Optional

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    firestore = None

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

class ApprovalQueue:
    """Manages pending optimization patches awaiting human approval."""
    
    def __init__(self):
        self.db = None
        if FIRESTORE_AVAILABLE:
            try:
                self.db = firestore.Client(project=PROJECT_ID)
                self.collection = self.db.collection("agem_approvals")
            except Exception:
                self.db = None
    
    def create(self, data: Dict) -> str:
        """Create a new approval request. Returns approval_id."""
        approval_id = str(uuid.uuid4())[:8]
        doc = {
            "approval_id": approval_id,
            "status": "pending",
            "created_at": time.time(),
            "resource": data.get("resource", "unknown"),
            "resource_type": data.get("type", "unknown"),
            "cws_before": data.get("cws_before", 0),
            "patch_action": data.get("patch", {}).get("action", "N/A"),
            "estimated_savings": data.get("patch", {}).get("estimated_savings", "N/A"),
            "patch": data.get("patch", {}),
            "validation": data.get("validation", {}),
            "trace_id": data.get("trace_id", ""),
        }
        if self.collection:
            self.collection.document(approval_id).set(doc)
        return approval_id
    
    def list_pending(self, limit: int = 50) -> List[Dict]:
        """List all pending approvals."""
        if not self.collection:
            return []
        try:
            docs = self.collection.where("status", "==", "pending").order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [{"id": d.id, **d.to_dict()} for d in docs]
        except Exception:
            return []
    
    def get(self, approval_id: str) -> Optional[Dict]:
        """Get a single approval by ID."""
        if not self.collection:
            return None
        try:
            doc = self.collection.document(approval_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None
    
    def approve(self, approval_id: str, approved_by: str = "human") -> bool:
        """Approve a pending patch and execute it."""
        if not self.collection:
            return False
        try:
            doc_ref = self.collection.document(approval_id)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            data = doc.to_dict()
            if data.get("status") != "pending":
                return False
            
            doc_ref.update({
                "status": "approved",
                "approved_at": time.time(),
                "approved_by": approved_by,
            })
            
            from .base import commit_patch_to_git, record_optimization_history
            import json
            patch = data.get("patch", {})
            commit_raw = commit_patch_to_git(json.dumps(patch))
            commit = json.loads(commit_raw)
            
            record_optimization_history(
                data.get("resource", "unknown"),
                data.get("resource_type", "unknown"),
                data.get("cws_before", 0),
                patch.get("action", ""),
                patch.get("estimated_savings", ""),
                commit.get("branch", "unknown"),
            )
            return True
        except Exception:
            return False
    
    def reject(self, approval_id: str, reason: str = "") -> bool:
        """Reject a pending patch."""
        if not self.collection:
            return False
        try:
            doc_ref = self.collection.document(approval_id)
            doc = doc_ref.get()
            if not doc.exists:
                return False
            data = doc.to_dict()
            if data.get("status") != "pending":
                return False
            doc_ref.update({
                "status": "rejected",
                "rejected_at": time.time(),
                "rejection_reason": reason,
            })
            return True
        except Exception:
            return False
    
    def get_stats(self) -> Dict:
        """Get queue statistics."""
        if not self.collection:
            return {"pending": 0, "approved": 0, "rejected": 0, "total": 0}
        try:
            pending = len(list(self.collection.where("status", "==", "pending").stream()))
            approved = len(list(self.collection.where("status", "==", "approved").stream()))
            rejected = len(list(self.collection.where("status", "==", "rejected").stream()))
            return {"pending": pending, "approved": approved, "rejected": rejected, "total": pending + approved + rejected}
        except Exception:
            return {"pending": 0, "approved": 0, "rejected": 0, "total": 0}
