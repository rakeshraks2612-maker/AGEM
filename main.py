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

def agem_scan(request=None):
    """Cloud Functions and Pub/Sub webhook entry point driving ADK Supervisor Loop."""
    from agem.agents.supervisor import AGEMSupervisor
    supervisor = AGEMSupervisor()
    cycle = supervisor.run_autonomous_loop(project_id=PROJECT_ID, auto_apply_safe=True)
    return json.dumps(cycle)


if __name__ == "__main__":
    import sys
    from agem.agents.supervisor import AGEMSupervisor

    print("\n" + "=" * 75)
    print("  🚀 AGEM — Autonomous Google-powered Efficiency Manager (ADK Mode)")
    print(f"  Target GCP Project: {PROJECT_ID} | Framework: Google ADK v2.6.3 (Gemini 3.5)")
    print("=" * 75 + "\n")

    supervisor = AGEMSupervisor()
    print("🧠 [ADK SUPERVISOR] Initiating autonomous closed-loop optimization cycle...")
    result = supervisor.run_autonomous_loop(project_id=PROJECT_ID, auto_apply_safe=True)
    
    print(f"   -> Evaluated {result['resources_evaluated']} GCP resources.")
    print(f"   -> Generated {result['patches_generated']} optimization candidate patches.")
    print(f"   -> Created {len(result['branches_committed'])} isolated GitOps branches.")
    
    if result.get("auto_applied_patches"):
        print(f"\n⚡ [SELECTIVE AUTONOMY] Auto-applied {len(result['auto_applied_patches'])} Tier-1 safe patches:")
        for ap in result["auto_applied_patches"]:
            print(f"   - {ap.get('resource_name')}: {ap.get('action')} -> {ap.get('verified_impact')}")
            
    if result.get("queued_patches"):
        print(f"\n🛡️ [APPROVAL QUEUE] Queued {len(result['queued_patches'])} Tier-2 patches for human review:")
        for qp in result["queued_patches"]:
            print(f"   - {qp.get('resource_name')}: {qp.get('action')} (Savings: {qp.get('estimated_savings')})")

    print("\n📝 [SUPERVISOR REASONING CHAIN]:")
    print(f"   \"{result.get('supervisor_reasoning')}\"")

    print("\n" + "=" * 75)
    print("  🎉 Autonomous Scan Complete! Run `python -m agem.server` for Web UI.")
    print("=" * 75 + "\n")

