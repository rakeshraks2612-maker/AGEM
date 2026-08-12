"""Agent Observability — stores agent reasoning traces in Firestore."""
import os
import time
import uuid
from typing import Dict, List, Any, Optional

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    firestore = None

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

class AgentTracer:
    \"\"\"Records every step of the agent pipeline for observability and debugging.\"\"\"
    
    def __init__(self):
        self.db = None
        if FIRESTORE_AVAILABLE:
            try:
                self.db = firestore.Client(project=PROJECT_ID)
                self.collection = self.db.collection("agem_traces")
            except Exception:
                self.db = None
    
    def start_trace(self, trace_id: str, metadata: Dict[str, Any] = None):
        \"\"\"Initialize a new trace.\"\"\"
        if not self.collection:
            return
        doc = {
            "trace_id": trace_id,
            "status": "running",
            "started_at": time.time(),
            "metadata": metadata or {},
            "steps": [],
        }
        try:
            self.collection.document(trace_id).set(doc)
        except Exception:
            pass
    
    def log_step(self, trace_id: str, agent_name: str, message: str, data: Dict[str, Any] = None):
        \"\"\"Log a single agent step.\"\"\"
        if not self.collection:
            return
        step = {
            "timestamp": time.time(),
            "agent": agent_name,
            "message": message,
            "data": data or {},
        }
        try:
            trace_ref = self.collection.document(trace_id)
            trace_ref.update({"steps": firestore.ArrayUnion([step])})
        except Exception:
            pass
    
    def end_trace(self, trace_id: str, summary: Dict[str, Any] = None):
        \"\"\"Finalize a trace with summary stats.\"\"\"
        if not self.collection:
            return
        try:
            self.collection.document(trace_id).update({
                "status": "completed",
                "ended_at": time.time(),
                "summary": summary or {},
            })
        except Exception:
            pass
    
    def get_trace(self, trace_id: str) -> Optional[Dict]:
        \"\"\"Retrieve a single trace.\"\"\"
        if not self.collection:
            return None
        try:
            doc = self.collection.document(trace_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None
    
    def list_traces(self, limit: int = 50) -> List[Dict]:
        \"\"\"List recent traces.\"\"\"
        if not self.collection:
            return []
        try:
            docs = self.collection.order_by("started_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [{"id": d.id, **d.to_dict()} for d in docs]
        except Exception:
            return []
