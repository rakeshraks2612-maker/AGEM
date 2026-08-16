"""Unit tests for AGEM AST Safety Validator."""
import unittest
from agem.validator import Validator, ValidationResult, validate
from agem.patcher import Patch


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.validator = Validator()

    def test_validator_clean_patch(self):
        patch = Patch(
            resource_type="Cloud SQL",
            resource_name="agem-demo-db",
            action="Downsize machine tier to db-n1-standard-1",
            patch_type="gcloud",
            before="settings.tier: db-n1-standard-2",
            after="gcloud sql instances patch agem-demo-db --tier=db-n1-standard-1 --project=agem-505107",
            estimated_savings="$25.00/month",
            rollback="gcloud sql instances patch agem-demo-db --tier=db-n1-standard-2 --project=agem-505107",
        )
        result = self.validator.validate(patch)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.passed)
        self.assertTrue(result.checks["non_destructive"])
        self.assertTrue(result.checks["has_rollback"])
        self.assertTrue(result.checks["has_savings"])

    def test_validator_reject_destructive_command(self):
        patch = Patch(
            resource_type="Cloud SQL",
            resource_name="agem-demo-db",
            action="Delete database instance",
            patch_type="gcloud",
            before="active",
            after="gcloud sql instances delete agem-demo-db --quiet",
            estimated_savings="$50.00/month",
            rollback="gcloud sql instances create agem-demo-db",
        )
        result = self.validator.validate(patch)
        self.assertFalse(result.passed)
        self.assertFalse(result.checks["non_destructive"])
        self.assertGreater(len(result.errors), 0)

    def test_validator_reject_missing_rollback(self):
        patch = Patch(
            resource_type="Cloud Run",
            resource_name="agem-service",
            action="Update service memory",
            patch_type="gcloud",
            before="memory: 4Gi",
            after="gcloud run services update agem-service --memory=512Mi",
            estimated_savings="$30.00/month",
            rollback="",
        )
        result = self.validator.validate(patch)
        self.assertFalse(result.passed)
        self.assertFalse(result.checks["has_rollback"])

    def test_batch_validate_function(self):
        patches = [
            {
                "id": "patch-1",
                "resource_name": "agem-db",
                "after": "gcloud sql instances patch agem-db --tier=db-f1-micro",
                "rollback": "gcloud sql instances patch agem-db --tier=db-n1-standard-2",
                "savings": 52.0,
            }
        ]
        self.assertTrue(validate(patches))


if __name__ == "__main__":
    unittest.main()
