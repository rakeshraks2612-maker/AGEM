# agem/state_manager.py
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
try:
    from google.cloud import firestore
    from google.cloud.firestore import FieldFilter
    HAS_FIRESTORE = True
except ImportError:
    firestore = None
    FieldFilter = None
    HAS_FIRESTORE = False

PROJECT_ID = "agem-505107"
COLLECTION_NAME = "agem_optimization_history"


class StateManager:
    """Firestore-backed state persistence for AGEM with in-memory fallback."""
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or PROJECT_ID
        self._memory_store = []
        if HAS_FIRESTORE and firestore is not None:
            try:
                self.db = firestore.Client(project=self.project_id)
                self.collection = self.db.collection(COLLECTION_NAME)
            except Exception:
                self.db = None
                self.collection = None
        else:
            self.db = None
            self.collection = None
    
    def record_optimization(self, resource_name: str, resource_type: str,
                           cws_before: float, patch_action: str,
                           estimated_savings: str, branch_name: str,
                           status: str = "committed") -> str:
        """Record an optimization in Firestore or memory."""
        record = {
            "resource_name": resource_name,
            "resource_type": resource_type,
            "cws_before": cws_before,
            "patch_action": patch_action,
            "estimated_savings": estimated_savings,
            "branch_name": branch_name,
            "status": status,
            "timestamp": datetime.utcnow().timestamp(),
            "project_id": self.project_id,
        }
        if self.collection is not None and firestore is not None:
            try:
                doc_ref = self.collection.document()
                fs_record = record.copy()
                fs_record["timestamp"] = firestore.SERVER_TIMESTAMP
                doc_ref.set(fs_record)
                return doc_ref.id
            except Exception:
                pass
        self._memory_store.append(record)
        return f"mem-{len(self._memory_store)}"
    
    def was_recently_optimized(self, resource_name: str, 
                               hours: int = 24) -> bool:
        """Check if a resource was optimized recently."""
        if self.collection is not None and FieldFilter is not None:
            try:
                query = self.collection.where(
                    filter=FieldFilter("resource_name", "==", resource_name)
                ).where(
                    filter=FieldFilter("status", "in", ["committed", "applied"])
                )
                for doc in query.stream():
                    data = doc.to_dict()
                    ts = data.get("timestamp")
                    if ts:
                        ts_seconds = ts.timestamp() if hasattr(ts, 'timestamp') else (ts if isinstance(ts, (int, float)) else 0)
                        cutoff = datetime.utcnow().timestamp() - (hours * 3600)
                        if ts_seconds > cutoff:
                            return True
                return False
            except Exception:
                pass
        cutoff = datetime.utcnow().timestamp() - (hours * 3600)
        for r in self._memory_store:
            if r.get("resource_name") == resource_name and r.get("status") in ["committed", "applied"]:
                if r.get("timestamp", 0) > cutoff:
                    return True
        return False
    
    def get_optimization_history(self, resource_name: Optional[str] = None,
                                  limit: int = 50) -> List[Dict[str, Any]]:
        """Get optimization history."""
        if self.collection is not None and firestore is not None:
            try:
                query = self.collection.order_by("timestamp", direction=firestore.Query.DESCENDING)
                if resource_name and FieldFilter is not None:
                    query = query.where(filter=FieldFilter("resource_name", "==", resource_name))
                results = []
                for doc in query.limit(limit).stream():
                    data = doc.to_dict()
                    data["id"] = doc.id
                    results.append(data)
                return results
            except Exception:
                pass
        filtered = [r for r in self._memory_store if not resource_name or r.get("resource_name") == resource_name]
        return filtered[-limit:]
    
    def get_total_estimated_savings(self) -> Dict[str, Any]:
        """Aggregate estimated savings."""
        if self.collection is not None and FieldFilter is not None:
            try:
                query = self.collection.where(
                    filter=FieldFilter("status", "in", ["committed", "applied"])
                )
                total_savings = 0.0
                count = 0
                for doc in query.stream():
                    data = doc.to_dict()
                    savings_str = data.get("estimated_savings", "")
                    match = re.search(r'\$([\d,]+(?:\.\d+)?)', savings_str)
                    if match:
                        total_savings += float(match.group(1).replace(',', ''))
                        count += 1
                return {
                    "total_optimizations": count,
                    "total_estimated_monthly_savings": f"${total_savings:.2f}/month",
                }
            except Exception:
                pass
        total_savings = 0.0
        count = 0
        for r in self._memory_store:
            if r.get("status") in ["committed", "applied"]:
                savings_str = r.get("estimated_savings", "")
                match = re.search(r'\$([\d,]+(?:\.\d+)?)', savings_str)
                if match:
                    total_savings += float(match.group(1).replace(',', ''))
                    count += 1
        return {
            "total_optimizations": count,
            "total_estimated_monthly_savings": f"${total_savings:.2f}/month",
        }
