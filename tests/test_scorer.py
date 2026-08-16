"""Unit tests for AGEM Cloud Waste Score (CWS) formula engine."""
import unittest
from agem.scorer import Scorer, CWSScore, compute_cws


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = Scorer()

    def test_scorer_initialization(self):
        self.assertEqual(self.scorer.WEIGHTS["cost_waste"], 0.35)
        self.assertEqual(self.scorer.WEIGHTS["performance"], 0.30)
        self.assertEqual(self.scorer.WEIGHTS["security"], 0.20)
        self.assertEqual(self.scorer.WEIGHTS["reliability"], 0.15)

    def test_score_cloud_sql_idle(self):
        metrics = {
            "cpu_utilization_7d_avg": 0.0428,
            "has_public_ip": False,
            "ssl_enforced": True,
            "automated_backups": True,
            "multi_zone": False,
        }
        score = self.scorer.score_cloud_sql(metrics)
        self.assertIsInstance(score, CWSScore)
        self.assertGreater(score.total, 0.0)
        self.assertGreater(score.cost_waste, 0.5)
        self.assertIsNotNone(score.dominant_bottleneck)

    def test_score_cloud_run_overprovisioned(self):
        metrics = {
            "memory_limit_gi": 4.0,
            "min_instances": 2,
            "cpu": "2",
        }
        score = self.scorer.score_cloud_run(metrics)
        self.assertGreater(score.total, 0.4)
        self.assertGreaterEqual(score.cost_waste, 0.8)
        self.assertIn("Rightsize", score.recommendation)

    def test_missing_metrics_neutral(self):
        """Missing security and reliability metrics should not penalize by default."""
        score = self.scorer.score_cloud_sql({"cpu_utilization_7d_avg": 0.85})
        self.assertEqual(score.security, 0.0)
        self.assertEqual(score.reliability, 0.0)

    def test_compute_cws_batch(self):
        resources = [
            {"id": "res-1", "type": "Cloud SQL", "metrics": {"cpu_utilization_7d_avg": 0.03}},
            {"id": "res-2", "type": "Cloud Run", "metrics": {"memory_limit_gi": 4, "min_instances": 2}},
        ]
        results = compute_cws(resources)
        self.assertEqual(len(results), 2)
        self.assertIn("cws", results[0])
        self.assertIn("cws_detail", results[0])


if __name__ == "__main__":
    unittest.main()
