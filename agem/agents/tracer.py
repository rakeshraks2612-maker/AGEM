"""Agent observability tracer."""
import time
from typing import List, Dict

class AgentTracer:
    """Records every step of the agent pipeline for observability."""
    def __init__(self):
        self._traces = []

    def record(self, step, detail, status="ok"):
        self._traces.append({
            "timestamp": time.time(),
            "step": step,
            "detail": detail,
            "status": status,
        })

    def get_traces(self):
        return self._traces[-100:]
