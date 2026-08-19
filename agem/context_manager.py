# agem/context_manager.py
"""Context and Memory Layer for AGEM.

Persists multi-turn reasoning chains, planning sessions, tool execution observations,
and system state in Google Cloud Firestore with thread-safe in-memory caching.
"""

import os
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from google.cloud import firestore
    from google.cloud.firestore import FieldFilter
    HAS_FIRESTORE = True
except ImportError:
    firestore = None
    FieldFilter = None
    HAS_FIRESTORE = False

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "agem-505107"))
COLLECTION_NAME = "agem_context_memory"


class ContextManager:
    """Manages cross-session context, reasoning traces, and autonomous plans."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ContextManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_id: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", PROJECT_ID))
        self._memory_store: List[Dict[str, Any]] = []
        self._plans: Dict[str, Any] = {}
        self.db = None
        self.collection = None

        if HAS_FIRESTORE and firestore is not None:
            try:
                self.db = firestore.Client(project=self.project_id)
                self.collection = self.db.collection(COLLECTION_NAME)
            except Exception:
                self.db = None
                self.collection = None
        self._initialized = True

    def log_trace(self, session_id: str, turn: int, phase: str,
                  reasoning: str, tool_called: Optional[str] = None,
                  tool_result_summary: Optional[str] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record an observable reasoning turn and tool observation."""
        entry = {
            "id": f"{session_id}-{turn}-{int(time.time()*1000)}",
            "session_id": session_id,
            "turn": turn,
            "phase": phase,  # planning | discovery | profiling | scoring | reasoning | patching | validation | execution | rollback
            "reasoning": reasoning,
            "tool_called": tool_called,
            "tool_result_summary": tool_result_summary,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "iso_time": datetime.utcnow().isoformat(),
            "project_id": self.project_id
        }

        # Store in memory for instant API queries
        self._memory_store.append(entry)
        if len(self._memory_store) > 200:
            self._memory_store = self._memory_store[-200:]

        # Persist asynchronously / safely to Firestore
        if self.collection is not None:
            try:
                self.collection.document(entry["id"]).set(entry)
            except Exception:
                pass

        return entry

    def record_plan(self, session_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store an autonomous plan (Plan -> Reason -> Act -> Learn)."""
        plan_record = {
            "session_id": session_id,
            "plan": plan_data,
            "timestamp": time.time(),
            "iso_time": datetime.utcnow().isoformat(),
            "project_id": self.project_id,
            "status": "active"
        }
        self._plans[session_id] = plan_record

        if self.db is not None:
            try:
                self.db.collection("agem_autonomous_plans").document(session_id).set(plan_record)
            except Exception:
                pass

        self.log_trace(
            session_id=session_id,
            turn=0,
            phase="planning",
            reasoning=f"Autonomous Strategy Formulated: {plan_data.get('strategy', 'Targeted CWS Optimization')}",
            tool_called="plan_optimizer",
            tool_result_summary=f"Plan generated with {len(plan_data.get('steps', []))} phases for {len(plan_data.get('priority_resources', []))} target resources.",
            metadata=plan_data
        )
        return plan_record

    def get_traces(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent chronological reasoning and tool traces."""
        if self.collection is not None:
            try:
                query = self.collection.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
                if session_id:
                    query = query.where(filter=FieldFilter("session_id", "==", session_id))
                docs = query.stream()
                results = [doc.to_dict() for doc in docs]
                if results:
                    return results
            except Exception:
                pass

        # In-memory fallback
        traces = self._memory_store
        if session_id:
            traces = [t for t in traces if t.get("session_id") == session_id]
        traces = sorted(traces, key=lambda x: x.get("timestamp", 0), reverse=True)
        return traces[:limit]

    def get_latest_plan(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the latest optimization plan."""
        if session_id and session_id in self._plans:
            return self._plans[session_id]
        if self._plans:
            return list(self._plans.values())[-1]
        return None
