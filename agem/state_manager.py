# agem/state_manager.py
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from google.cloud import firestore


PROJECT_ID = "agem-505107"
COLLECTION_NAME = "agem_optimization_history"


class StateManager:
    """Firestore-backed state persistence for AGEM.
    
    Remembers past optimizations so AGEM doesn't re-patch
    the same resource twice. Provides audit trail.
    """
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or PROJECT_ID
        self.db = firestore.Client(project=self.project_id)
        self.collection = self.db.collection(COLLECTION_NAME)
    
    def record_optimization(self, resource_name: str, resource_type: str,
                           cws_before: float, patch_action: str,
                           estimated_savings: str, branch_name: str,
                           status: str = "committed") -> str:
        """Record an optimization in Firestore."""
        doc_ref = self.collection.document()
        doc_ref.set({
            "resource_name": resource_name,
            "resource_type": resource_type,
            "cws_before": cws_before,
            "patch_action": patch_action,
            "estimated_savings": estimated_savings,
            "branch_name": branch_name,
            "status": status,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "project_id": self.project_id,
        })
        return doc_ref.id
    
    def was_recently_optimized(self, resource_name: str, 
                               hours: int = 24) -> bool:
        """Check if a resource was optimized recently."""
        cutoff = datetime.utcnow().timestamp() - (hours * 3600)
        
        docs = self.collection.where("resource_name", "==", resource_name)\
                             .where("status", "in", ["committed", "applied"])\
                             .stream()
        
        for doc in docs:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts:
                # Firestore timestamp to unix
                ts_seconds = ts.timestamp() if hasattr(ts, 'timestamp') else 0
                if ts_seconds > cutoff:
                    return True
        return False
    
    def get_optimization_history(self, resource_name: Optional[str] = None,
                                  limit: int = 50) -> List[Dict[str, Any]]:
        """Get optimization history, optionally filtered by resource."""
        query = self.collection.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        if resource_name:
            query = query.where("resource_name", "==", resource_name)
        
        results = []
        for doc in query.limit(limit).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results
    
    def get_total_estimated_savings(self) -> Dict[str, Any]:
        """Aggregate estimated savings across all optimizations."""
        docs = self.collection.where("status", "in", ["committed", "applied"]).stream()
        
        total_savings = 0.0
        count = 0
        
        for doc in docs:
            data = doc.to_dict()
            savings_str = data.get("estimated_savings", "")
            # Extract dollar amount from strings like "~$50/month"
            import re
            match = re.search(r'\$([\d,]+(?:\.\d+)?)', savings_str)
            if match:
                total_savings += float(match.group(1).replace(',', ''))
                count += 1
        
        return {
            "total_optimizations": count,
            "total_estimated_monthly_savings": f"${total_savings:.2f}/month",
        }
