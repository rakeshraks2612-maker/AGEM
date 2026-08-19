"""Integration tests for AGEM full closed-loop pipeline and server routes."""

import unittest
from agem.agents.supervisor import AGEMSupervisor
from agem.server import app


class TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.supervisor = AGEMSupervisor()
        self.client = app.test_client()

    def test_full_autonomous_loop_execution(self):
        result = self.supervisor.run_autonomous_loop(project_id="test-proj-505", auto_apply_safe=True)
        self.assertEqual(result["status"], "success")
        self.assertIn("plan", result)
        self.assertIn("observations", result)
        self.assertIn("discovery", result["observations"])
        self.assertIn("profiling", result["observations"])
        self.assertIn("scoring", result["observations"])
        self.assertIn("patching", result["observations"])
        self.assertIn("validation", result["observations"])
        self.assertIn("gitops", result["observations"])
        self.assertTrue(result["closed_loop_verified"])
        self.assertTrue(len(result["branches_committed"]) >= 1 or len(result["queued_patches"]) >= 1 or len(result["auto_applied_patches"]) >= 1)

    def test_server_health_and_plan_endpoints(self):
        res_health = self.client.get("/api/health")
        self.assertEqual(res_health.status_code, 200)
        data_health = res_health.get_json()
        self.assertEqual(data_health["status"], "healthy")
        self.assertEqual(data_health["adk_version"], "2.6.3")

        res_plan = self.client.get("/api/plan")
        self.assertEqual(res_plan.status_code, 200)
        data_plan = res_plan.get_json()
        self.assertIn("plan", data_plan)

        res_resources = self.client.get("/api/resources")
        self.assertEqual(res_resources.status_code, 200)
        data_res = res_resources.get_json()
        self.assertEqual(data_res["count"], 15)


if __name__ == "__main__":
    unittest.main()
