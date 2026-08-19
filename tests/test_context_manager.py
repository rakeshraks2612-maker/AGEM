"""Unit tests for Context and Memory Layer (ContextManager)."""

import unittest
import time
from agem.context_manager import ContextManager


class TestContextManager(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager(project_id="test-project-123")

    def test_log_trace_and_retrieval(self):
        session_id = f"test-session-{int(time.time()*1000)}"
        entry = self.cm.log_trace(
            session_id=session_id,
            turn=1,
            phase="discovery",
            reasoning="Testing multi-turn reasoning persistence.",
            tool_called="discover_resources",
            tool_result_summary="Found 3 test assets."
        )
        self.assertEqual(entry["session_id"], session_id)
        self.assertEqual(entry["phase"], "discovery")
        self.assertEqual(entry["tool_called"], "discover_resources")

        traces = self.cm.get_traces(session_id=session_id)
        self.assertTrue(len(traces) >= 1)
        self.assertEqual(traces[0]["session_id"], session_id)

    def test_record_plan(self):
        session_id = f"plan-session-{int(time.time()*1000)}"
        plan_data = {
            "strategy": "High-Efficiency Test Plan",
            "steps": ["discovery", "scoring", "patching"],
            "priority_resources": ["test-service-1"]
        }
        plan_record = self.cm.record_plan(session_id, plan_data)
        self.assertEqual(plan_record["session_id"], session_id)
        self.assertEqual(plan_record["plan"]["strategy"], "High-Efficiency Test Plan")

        latest = self.cm.get_latest_plan(session_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["plan"]["strategy"], "High-Efficiency Test Plan")


if __name__ == "__main__":
    unittest.main()
