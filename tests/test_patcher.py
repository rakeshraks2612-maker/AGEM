"""Unit tests for AGEM Gemini Patch Generator & Fallback Parser."""
import unittest
from agem.patcher import Patcher, Patch, generate


class TestPatcher(unittest.TestCase):
    def test_fallback_patch_sql(self):
        patcher = Patcher.__new__(Patcher)
        resource = {
            "name": "projects/agem-505107/instances/agem-demo-db",
            "type": "Cloud SQL",
            "metrics": {"cpu": "4.3%"}
        }
        score = {"total": 0.46, "dominant_bottleneck": "cost", "recommendation": "downsize"}
        patch = patcher._fallback_patch(resource, score)
        self.assertIsInstance(patch, Patch)
        self.assertIn("gcloud sql", patch.after)
        self.assertTrue("db-f1-micro" in patch.after or "db-n1-standard-1" in patch.after)
        self.assertTrue(hasattr(patch, "rollback") and len(patch.rollback) > 0)
        self.assertTrue("$52.00/month" in patch.estimated_savings or "$25.00/month" in patch.estimated_savings)

    def test_fallback_patch_cloud_run(self):
        patcher = Patcher.__new__(Patcher)
        resource = {
            "name": "projects/agem-505107/locations/us-central1/services/agem-demo-service",
            "type": "Cloud Run",
            "metrics": {"memory_limit_gi": 4, "min_instances": 2}
        }
        score = {"total": 0.80, "dominant_bottleneck": "cost", "recommendation": "rightsize"}
        patch = patcher._fallback_patch(resource, score)
        self.assertIsInstance(patch, Patch)
        self.assertIn("--min-instances=0", patch.after)
        self.assertIn("--memory=512Mi", patch.after)
        self.assertIn("--min-instances=2", patch.rollback)
        self.assertEqual(patch.estimated_savings, "$72.00/month")

    def test_patch_parsing_structure(self):
        patcher = Patcher.__new__(Patcher)
        sample_llm_output = """PATCH_TYPE: gcloud
ACTION: Downsize idle Cloud SQL instance
BEFORE: tier: db-n1-standard-2
AFTER: gcloud sql instances patch demo-db --tier=db-n1-standard-1
ESTIMATED_SAVINGS: $25.00/month
ROLLBACK: gcloud sql instances patch demo-db --tier=db-n1-standard-2
SAFETY_NOTES: Zero downtime rolling restart"""
        
        parsed = patcher._parse_patch(sample_llm_output, {"name": "demo-db", "type": "Cloud SQL"}, {})
        self.assertEqual(parsed.patch_type, "gcloud")
        self.assertEqual(parsed.action, "Downsize idle Cloud SQL instance")
        self.assertIn("db-n1-standard-1", parsed.after)
        self.assertEqual(parsed.estimated_savings, "$25.00/month")

    def test_generate_batch(self):
        resources = [
            {"name": "agem-db", "type": "Cloud SQL", "metrics": {"cpu": "3.8%"}},
            {"name": "agem-run", "type": "Cloud Run", "metrics": {"memory_limit_gi": 4}},
        ]
        patches = generate(resources)
        self.assertEqual(len(patches), 2)
        self.assertIn("diff", patches[0])
        self.assertIn("rollback", patches[0])
        self.assertGreater(patches[0]["savings"], 0)


if __name__ == "__main__":
    unittest.main()
