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
        
        # 1. Discover (Returns structured dict)
        disc_res = self.sup.agent.tools[0]()
        self.assertIsInstance(disc_res, dict)
        self.assertEqual(disc_res.get("tool"), "discover_resources")
        self.assertIn("Discovered", str(disc_res))
        
        # 2. Profile
        prof_res = self.sup.agent.tools[1]()
        self.assertIsInstance(prof_res, dict)
        self.assertEqual(prof_res.get("tool"), "profile_metrics")
        self.assertIn("profiled_count", prof_res)
        
        # 3. Score
        score_res = self.sup.agent.tools[2]()
        self.assertIsInstance(score_res, dict)
        self.assertEqual(score_res.get("tool"), "score_waste")
        self.assertIn("CWS", str(score_res))
        
        # 4. Patch
        patch_res = self.sup.agent.tools[3]()
        self.assertIsInstance(patch_res, dict)
        self.assertEqual(patch_res.get("tool"), "generate_patch")
        
        # 5. Validate
        val_res = self.sup.agent.tools[4]()
        self.assertIsInstance(val_res, dict)
        self.assertEqual(val_res.get("tool"), "validate_safety")
        self.assertTrue("passed" in str(val_res).lower() or "safety" in str(val_res).lower())
        
        # 6. Commit
        git_res = self.sup.agent.tools[5]()
        self.assertIsInstance(git_res, dict)
        self.assertEqual(git_res.get("tool"), "commit_git")
        
        # 7. Execute
        exec_res = self.sup.agent.tools[6]()
        self.assertIsInstance(exec_res, dict)
        self.assertEqual(exec_res.get("tool"), "execute_patch")


if __name__ == "__main__":
    unittest.main()
