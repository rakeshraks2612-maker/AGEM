import os
import json
import time
import subprocess
from typing import Dict, Any, List
from google.cloud import asset_v1, monitoring_v3
from agem.scorer import Scorer
from agem.patcher import Patcher
from agem.validator import Validator
from agem.git_committer import GitCommitter
from agem.executor import Executor
from agem.state_manager import StateManager

PROJECT_ID = "agem-505107"

def discover_resources() -> List[Dict[str, Any]]:
    client = asset_v1.AssetServiceClient()
    parent = f"projects/{PROJECT_ID}"
    request = asset_v1.ListAssetsRequest(
        parent=parent,
        asset_types=[
            "sqladmin.googleapis.com/Instance",
            "run.googleapis.com/Service",
        ],
        content_type=asset_v1.ContentType.RESOURCE,
    )
    resources = []
    for asset in client.list_assets(request=request):
        resources.append({
            "name": asset.name,
            "type": asset.asset_type,
            "data": dict(asset.resource.data) if asset.resource.data else {},
        })
    return resources

def get_cloud_sql_cpu(instance_name: str, days: int = 7) -> float:
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{PROJECT_ID}"
    now = time.time()
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(now)},
        "start_time": {"seconds": int(now - (days * 86400))},
    })
    filter_str = (
        f'metric.type="cloudsql.googleapis.com/database/cpu/utilization" '
        f'AND resource.labels.database_id="{PROJECT_ID}:{instance_name}"'
    )
    results = client.list_time_series(
        request={
            "name": project_name,
            "filter": filter_str,
            "interval": interval,
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )
    points = []
    for series in results:
        for point in series.points:
            val = point.value.double_value
            if val is not None:
                points.append(val)
    return round(sum(points) / len(points), 4) if points else 0.0

def agem_scan(request):
    """Cloud Functions entry point."""
    start = time.time()
    
    scorer = Scorer()
    patcher = Patcher()
    validator = Validator()
    committer = GitCommitter()
    executor = Executor(dry_run=True)
    state_manager = StateManager()
    
    resources = discover_resources()
    results = []
    approved = 0
    
    for r in resources:
        res_type = r['type'].split('/')[-1]
        name = r['name'].split('/')[-1]
        item = {"resource_type": res_type, "name": name, "status": "unknown"}
        
        if "sqladmin" in r['type']:
            cpu = get_cloud_sql_cpu(name)
            item["cpu_7d_avg"] = f"{cpu * 100:.2f}%"
            
            if state_manager.was_recently_optimized(name, hours=24):
                item["status"] = "skipped"
                item["reason"] = "optimized in last 24h"
                results.append(item)
                continue
            
            score = scorer.score_cloud_sql({"cpu_utilization_7d_avg": cpu})
            item["cws_score"] = score.total
            
            patch = patcher.generate_patch(
                {"type": r['type'], "name": r['name'], "metrics": {"cpu": cpu}},
                {"total": score.total, "dominant_bottleneck": score.dominant_bottleneck, "recommendation": score.recommendation}
            )
            
            validation = validator.validate(patch, r)
            if validation.passed:
                commit = committer.commit_patch(patch, name)
                if commit.success:
                    state_manager.record_optimization(
                        resource_name=name,
                        resource_type="cloud_sql",
                        cws_before=score.total,
                        patch_action=patch.action,
                        estimated_savings=patch.estimated_savings,
                        branch_name=commit.branch,
                        status="committed",
                    )
                    item["status"] = "approved"
                    item["branch"] = commit.branch
                    item["savings"] = patch.estimated_savings
                    approved += 1
                else:
                    item["status"] = "commit_failed"
            else:
                item["status"] = "rejected"
        
        results.append(item)
    
    savings = state_manager.get_total_estimated_savings()
    
    return json.dumps({
        "project": PROJECT_ID,
        "resources_scanned": len(resources),
        "patches_approved": approved,
        "total_estimated_monthly_savings": savings["total_estimated_monthly_savings"],
        "scan_duration_sec": round(time.time() - start, 2),
        "results": results,
    })


if __name__ == "__main__":
    import sys
    from agem import profiler, scorer, patcher, validator, git_committer, executor
    from agem.agents.supervisor import AGEMSupervisor

    print("\n" + "=" * 70)
    print("  🚀 AGEM — Autonomous Google-powered Efficiency Manager (CLI Mode)")
    print(f"  Target GCP Project: {PROJECT_ID} | Framework: Google ADK v2.6.3")
    print("=" * 70 + "\n")

    print("🔍 [Stage 1/7: DISCOVER] Ingesting GCP fleet topology...")
    resources = profiler.discover(PROJECT_ID)
    print(f"   -> Discovered {len(resources)} active endpoints.")

    print("\n📊 [Stage 2/7: PROFILE] Aggregating 7-day Cloud Monitoring telemetry...")
    profiled = profiler.profile(PROJECT_ID)
    for r in profiled:
        print(f"   - {r.get('id', 'resource')} ({r.get('type', 'GCP')}) -> Metrics: {r.get('metrics', {})}")

    print("\n⚖️ [Stage 3/7: SCORE] Calculating Cloud Waste Score (CWS)...")
    scored = scorer.compute_cws(profiled)
    for r in scored:
        print(f"   - {r.get('id')}: CWS={r.get('cws', 0.5):.2f}/1.0 ({r.get('cws_detail', {}).get('dominant_bottleneck', 'Waste')})")

    print("\n🧠 [Stage 4/7: SYNTHESIZE] Generating Gemini 3.5 rightsizing patches...")
    patches = patcher.generate(scored)
    print(f"   -> Synthesized {len(patches)} optimization candidate patches.")

    print("\n🛡️ [Stage 5/7: VALIDATE] Executing AST syntax & non-destructive safety checks...")
    for p in patches:
        v = validator.validate(p)
        print(f"   - {p.get('resource_id')}: {'✅ PASSED' if v else '❌ FAILED'}")

    print("\n📦 [Stage 6/7: GITOPS COMMIT] Committing patch manifests to isolated Git branches...")
    for p in patches:
        b = git_committer.commit(p)
        print(f"   - Branch: {b} -> Savings: ${p.get('savings', 0):.2f}/mo")

    print("\n⚡ [Stage 7/7: ADK SUPERVISOR] Initializing ADK Supervisor Loop...")
    supervisor = AGEMSupervisor()
    print(f"   Supervisor initialized: {supervisor.agent.name} with {len(supervisor.agent.tools)} tools.")

    print("\n" + "=" * 70)
    print("  🎉 Autonomous Scan Complete! Run `python -m agem.server` for Web UI.")
    print("=" * 70 + "\n")

