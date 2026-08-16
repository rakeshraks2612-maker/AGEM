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
        # Successful optimization (lower waste)
        ok, msg = self.executor.reprofile_and_validate("agem-db", base_cws=0.80, opt_cws=0.25)
        self.assertTrue(ok)
        self.assertIn("Verified CWS efficiency gain", msg)
        
        # Regression (higher waste)
        reg_ok, reg_msg = self.executor.reprofile_and_validate("agem-db", base_cws=0.30, opt_cws=0.60)
        self.assertFalse(reg_ok)
        self.assertIn("Regression detected", reg_msg)


if __name__ == "__main__":
    unittest.main()
