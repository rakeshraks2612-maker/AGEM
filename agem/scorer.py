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
    """Cloud Waste Score (CWS) Calculator.
    Formula: CWS = 0.35*Cost + 0.30*Perf + 0.20*Sec + 0.15*Rel
    """
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
        raw_cpu = metrics.get("cpu_utilization_7d_avg", metrics.get("cpu", 0.04))
        if isinstance(raw_cpu, str):
            raw_str = raw_cpu.replace("%", "").strip()
            try:
                cpu = float(raw_str) / 100.0 if float(raw_str) > 1.0 else float(raw_str)
            except Exception:
                cpu = 0.04
        else:
            cpu = float(raw_cpu)
        
        # 1. Cost Waste: underutilized CPU / oversized tier
        cost_waste = min(1.0, max(0.0, 1.0 - (cpu / self.THRESHOLDS["min_cpu"])))
        
        # 2. Performance Waste: wasted allocation capacity
        performance = min(1.0, max(0.0, 1.0 - (cpu / self.THRESHOLDS["min_cpu"])))
        
        # 3. Security Risk: public IP exposed, SSL enforcement, unencrypted disk
        has_public_ip = metrics.get("has_public_ip", True)
        ssl_enforced = metrics.get("ssl_enforced", False)
        security = 0.0
        if has_public_ip:
            security += 0.50
        if not ssl_enforced:
            security += 0.30
        security = min(1.0, security)
        
        # 4. Reliability Risk: automated backups disabled, single zone
        automated_backups = metrics.get("automated_backups", False)
        multi_zone = metrics.get("multi_zone", False)
        reliability = 0.0
        if not automated_backups:
            reliability += 0.50
        if not multi_zone:
            reliability += 0.30
        reliability = min(1.0, reliability)
        
        total = (
            self.WEIGHTS["cost_waste"] * cost_waste +
            self.WEIGHTS["performance"] * performance +
            self.WEIGHTS["security"] * security +
            self.WEIGHTS["reliability"] * reliability
        )
        
        scores = {
            "cost_waste": cost_waste,
            "performance": performance,
            "security": security,
            "reliability": reliability,
        }
        dominant = max(scores, key=scores.get)
        
        if total > 0.60:
            rec = "CRITICAL: Severe idle compute, exposed public IP, and missing HA backups. Immediate right-sizing required."
        elif total > 0.40:
            rec = "HIGH: Severely over-provisioned. Downsize compute tier and enable automated backup schedules."
        elif total > 0.20:
            rec = "MEDIUM: Under-utilized compute budget. Monitor and rightsizing recommended."
        else:
            rec = "OPTIMAL: Resource is well-utilized and adhering to security & reliability policies."
        
        return CWSScore(
            total=round(total, 2),
            cost_waste=round(cost_waste, 2),
            performance=round(performance, 2),
            security=round(security, 2),
            reliability=round(reliability, 2),
            dominant_bottleneck=dominant,
            recommendation=rec,
        )

    def score_cloud_run(self, metrics: Dict[str, Any]) -> CWSScore:
        memory_gi = float(metrics.get("memory_limit_gi", 4.0))
        min_instances = int(metrics.get("min_instances", 2))
        cpu = metrics.get("cpu", "2")
        
        # Cost waste: oversized memory and idle min instances
        cost_waste = 0.0
        if memory_gi > 1.0:
            cost_waste += 0.45
        if min_instances > 0:
            cost_waste += 0.40
        cost_waste = min(1.0, cost_waste)
        
        # Performance waste: idle container allocation
        performance = min(1.0, cost_waste * 0.85)
        
        # Security: ingress mode & authentication
        allow_unauth = metrics.get("allow_unauthenticated", True)
        security = 0.40 if allow_unauth else 0.10
        
        # Reliability: concurrency & multi-region
        concurrency = metrics.get("concurrency", 80)
        reliability = 0.35 if concurrency > 100 or min_instances == 0 else 0.15
        
        total = (
            self.WEIGHTS["cost_waste"] * cost_waste +
            self.WEIGHTS["performance"] * performance +
            self.WEIGHTS["security"] * security +
            self.WEIGHTS["reliability"] * reliability
        )
        
        scores = {"cost_waste": cost_waste, "performance": performance, "security": security, "reliability": reliability}
        dominant = max(scores, key=scores.get)
        
        rec = "Rightsize Cloud Run memory to 512Mi and enable scale-to-zero (min-instances=0) to eliminate idle runtime charges."
        
        return CWSScore(
            total=round(total, 2),
            cost_waste=round(cost_waste, 2),
            performance=round(performance, 2),
            security=round(security, 2),
            reliability=round(reliability, 2),
            dominant_bottleneck=dominant,
            recommendation=rec,
        )

    def score_bigquery(self, metrics: Dict[str, Any]) -> CWSScore:
        slots_util = float(metrics.get("slots_utilization", 0.12))
        unpartitioned_gb = float(metrics.get("unpartitioned_gb", 45.0))
        has_expiration = metrics.get("has_table_expiration", False)
        
        # Cost waste: unused reserved slots or unpartitioned full table scans
        cost_waste = 0.0
        if slots_util < 0.20:
            cost_waste += 0.50
        if unpartitioned_gb > 10.0:
            cost_waste += 0.35
        cost_waste = min(1.0, cost_waste)
        
        # Performance waste: full scans
        performance = 0.45 if unpartitioned_gb > 20.0 else 0.15
        
        # Security: dataset access policies
        public_access = metrics.get("public_access", False)
        security = 0.60 if public_access else 0.10
        
        # Reliability: partition expiration & dataset multi-region replication
        reliability = 0.40 if not has_expiration else 0.10
        
        total = (
            self.WEIGHTS["cost_waste"] * cost_waste +
            self.WEIGHTS["performance"] * performance +
            self.WEIGHTS["security"] * security +
            self.WEIGHTS["reliability"] * reliability
        )
        
        scores = {"cost_waste": cost_waste, "performance": performance, "security": security, "reliability": reliability}
        dominant = max(scores, key=scores.get)
        
        rec = "Enable table partition expiration and switch to flat-rate slot commitments with autoscale to prevent on-demand query cost spikes."
        
        return CWSScore(
            total=round(total, 2),
            cost_waste=round(cost_waste, 2),
            performance=round(performance, 2),
            security=round(security, 2),
            reliability=round(reliability, 2),
            dominant_bottleneck=dominant,
            recommendation=rec,
        )
    
    def score_resource(self, resource: Dict[str, Any]) -> CWSScore:
        rtype = resource.get("type", "").lower()
        metrics = resource.get("metrics", {})
        if "sql" in rtype:
            return self.score_cloud_sql(metrics)
        elif "run" in rtype:
            return self.score_cloud_run(metrics)
        elif "bigquery" in rtype or "dataset" in rtype:
            return self.score_bigquery(metrics)
        else:
            # General GCP resource scoring
            return self.score_cloud_sql(metrics)

