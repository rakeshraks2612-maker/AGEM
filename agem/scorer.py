# agem/scorer.py
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class CWSScore:
    total: float
    cost_waste: float
    performance: float
    security: float
    reliability: float
    dominant_bottleneck: str
    recommendation: str


class Scorer:
    WEIGHTS = {
        "cost_waste": 0.35,
        "performance": 0.30,
        "security": 0.20,
        "reliability": 0.15,
    }
    
    THRESHOLDS = {
        "min_cpu": 0.15,
        "max_cpu": 0.85,
    }
    
    def score_cloud_sql(self, metrics: Dict[str, Any]) -> CWSScore:
        cpu = metrics.get("cpu_utilization_7d_avg", 0)
        
        cost_waste = max(0, 1.0 - (cpu / self.THRESHOLDS["min_cpu"]))
        performance = max(0, 1.0 - (cpu / self.THRESHOLDS["min_cpu"]))
        
        total = (
            self.WEIGHTS["cost_waste"] * cost_waste +
            self.WEIGHTS["performance"] * performance
        )
        
        scores = {"cost_waste": cost_waste, "performance": performance, "security": 0.0, "reliability": 0.0}
        dominant = max(scores, key=scores.get)
        
        if cpu < 0.05:
            rec = "CRITICAL: Instance is essentially idle. Downsize to db-f1-micro or delete."
        elif cpu < 0.15:
            rec = "HIGH: Severely over-provisioned. Consider db-n1-standard-1 or db-f1-micro."
        elif cpu < 0.30:
            rec = "MEDIUM: Under-utilized. Monitor and consider rightsizing."
        else:
            rec = "OK: Utilization within acceptable range."
        
        return CWSScore(
            total=round(total, 2),
            cost_waste=round(cost_waste, 2),
            performance=round(performance, 2),
            security=0.0,
            reliability=0.0,
            dominant_bottleneck=dominant,
            recommendation=rec,
        )
