"""Unit tests for Google ADK Supervisor Agent and Tool Registration."""
import unittest
from agem.agents.supervisor import AGEMSupervisor


class TestSupervisor(unittest.TestCase):
    def setUp(self):
        self.sup = AGEMSupervisor()

    def test_supervisor_initialization(self):
        self.assertEqual(self.sup.agent.name, "agem_supervisor")
        self.assertEqual(self.sup.agent.model, "gemini-3.5-flash")
        self.assertEqual(len(self.sup.agent.tools), 7)
        tool_names = [t.__name__ for t in self.sup.agent.tools]
        self.assertIn("discover_resources", tool_names)
        self.assertIn("profile_metrics", tool_names)
        self.assertIn("score_waste", tool_names)
        self.assertIn("generate_patch", tool_names)
        self.assertIn("validate_safety", tool_names)
        self.assertIn("commit_git", tool_names)
        self.assertIn("execute_patch", tool_names)

    def test_supervisor_tool_execution_flow(self):
        # Pre-seed single resource for instantaneous execution
        self.sup._state["resources"] = [
            {"id": "agem-db", "type": "Cloud SQL", "name": "agem-db", "metrics": {"cpu": "4%"}}
        ]
        
        # 1. Discover
        disc_res = self.sup.agent.tools[0]()
        self.assertIn("Discovered", disc_res)
        
        # 2. Profile
        prof_res = self.sup.agent.tools[1]()
        self.assertIn("Profiled", prof_res)
        
        # 3. Score
        score_res = self.sup.agent.tools[2]()
        self.assertTrue("Computed CWS" in score_res or "CWS" in score_res)
        
        # 4. Validate
        val_res = self.sup.agent.tools[4]()
        self.assertTrue("Safety" in val_res or "passed" in val_res.lower())
        
        # 5. Commit
        git_res = self.sup.agent.tools[5]()
        self.assertTrue("Committed" in git_res or "Git" in git_res)
        
        # 6. Execute
        exec_res = self.sup.agent.tools[6]()
        self.assertTrue("execution" in exec_res.lower() or "dry-run" in exec_res.lower() or "ready" in exec_res.lower())


if __name__ == "__main__":
    unittest.main()
