"""Unit tests for AGEM Execution and Rollback Engine."""
import unittest
from agem.executor import Executor, ExecutionResult, execute, execute_rollback


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = Executor(dry_run=True)

    def test_executor_dry_run(self):
        patch = {
            "resource_id": "agem-demo-service",
            "diff": {"after": "gcloud run services update agem-demo-service --memory=512Mi"},
            "after": "gcloud run services update agem-demo-service --memory=512Mi",
            "rollback": "gcloud run services update agem-demo-service --memory=4Gi",
        }
        
        result = self.executor.execute(patch)
        self.assertIsInstance(result, ExecutionResult)
        self.assertTrue(result.success)
        self.assertIn("[DRY-RUN]", result.stdout)
        self.assertIn("gcloud run services update", result.command)

    def test_executor_rollback_dry_run(self):
        patch = {
            "resource_id": "agem-demo-service",
            "rollback": "gcloud run services update agem-demo-service --min-instances=2",
        }
        
        result = self.executor.execute_rollback(patch)
        self.assertTrue(result.success)
        self.assertIn("[DRY-RUN]", result.stdout)
        self.assertIn("--min-instances=2", result.command)

    def test_reprofile_and_validate(self):
        # Successful optimization (lower waste: 0.80 -> dynamic post_cws <= 0.80)
        ok, post_cws, msg = self.executor.reprofile_and_validate({"resource_name": "agem-db"}, base_cws=0.80)
        self.assertTrue(ok)
        self.assertLess(post_cws, 0.80)
        self.assertIn("Verified CWS waste reduction", msg)
        
        # Regression with Auto-Rollback (higher waste: base_cws=0.20 < post_cws triggers rollback)
        patch = {"resource_name": "agem-db", "rollback": "gcloud run services update agem-db --min-instances=2"}
        reg_ok, reg_cws, reg_msg = self.executor.reprofile_and_validate(patch, base_cws=0.20)
        self.assertFalse(reg_ok)
        self.assertGreaterEqual(reg_cws, 0.20)
        self.assertIn("AUTO-ROLLBACK TRIGGERED", reg_msg)


if __name__ == "__main__":
    unittest.main()
