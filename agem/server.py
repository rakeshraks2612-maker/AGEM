# agem/server.py
import os
import json
import time
import subprocess
from typing import Dict, Any, List
from flask import Flask, jsonify
from google.cloud import asset_v1, monitoring_v3
from agem.scorer import Scorer
from agem.patcher import Patcher
from agem.validator import Validator
from agem.git_committer import GitCommitter
from agem.executor import Executor
from agem.state_manager import StateManager

app = Flask(__name__)
PROJECT_ID = "agem-505107"


def discover_resources() -> List[Dict[str, Any]]:
    client = asset_v1.AssetServiceClient()
    parent = f"projects/{PROJECT_ID}"
    request = asset_v1.ListAssetsRequest(
        parent=parent,
        asset_types=[
            "sqladmin.googleapis.com/Instance",
            "run.googleapis.com/Service",
            "bigquery.googleapis.com/Dataset",
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


def get_cloud_run_config(service_name: str) -> Dict[str, Any]:
    result = subprocess.run([
        "gcloud", "run", "services", "describe", service_name,
        "--region=us-central1", "--format=json"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return {"memory_limit_gi": 1, "min_instances": 0}
    data = json.loads(result.stdout)
    containers = data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [{}])
    limits = containers[0].get("resources", {}).get("limits", {})
    min_scale = data.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {}).get("autoscaling.knative.dev/minScale", "0")
    memory = limits.get("memory", "512Mi")
    if memory.endswith("Gi"):
        memory_gi = int(memory.replace("Gi", ""))
    elif memory.endswith("Mi"):
        memory_gi = int(memory.replace("Mi", "")) / 1024
    else:
        memory_gi = 1
    return {
        "memory_limit_gi": memory_gi,
        "min_instances": int(min_scale),
        "cpu": limits.get("cpu", "1"),
    }


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "AGEM is live", "project": PROJECT_ID})


@app.route("/scan", methods=["POST", "GET"])
def scan():
    """Trigger AGEM scan. Returns JSON results."""
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
    skipped = 0
    
    for r in resources:
        res_type = r['type'].split('/')[-1]
        name = r['name'].split('/')[-1]
        item = {
            "resource_type": res_type,
            "name": name,
            "action": "none",
            "status": "unknown"
        }
        
        if "sqladmin" in r['type']:
            cpu = get_cloud_sql_cpu(name)
            item["cpu_7d_avg"] = f"{cpu * 100:.2f}%"
            
            if state_manager.was_recently_optimized(name, hours=24):
                item["status"] = "skipped"
                item["reason"] = "optimized in last 24h"
                skipped += 1
                results.append(item)
                continue
            
            score = scorer.score_cloud_sql({"cpu_utilization_7d_avg": cpu})
            item["cws_score"] = score.total
            item["bottleneck"] = score.dominant_bottleneck
            
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
                item["validation"] = validation.checks
        
        elif "run" in r['type']:
            config = get_cloud_run_config("agem-demo-service")
            item["memory_gi"] = config["memory_limit_gi"]
            item["min_instances"] = config["min_instances"]
            
            waste = 0.5 if config["memory_limit_gi"] > 2 else 0.0
            waste += 0.3 if config["min_instances"] > 0 else 0.0
            
            patch = patcher.generate_patch(
                {"type": r['type'], "name": r['name'], "metrics": config},
                {"total": waste, "dominant_bottleneck": "cost_waste", "recommendation": "Rightsize Cloud Run service"}
            )
            
            validation = validator.validate(patch, r)
            if validation.passed:
                commit = committer.commit_patch(patch, "agem-demo-service")
                if commit.success:
                    state_manager.record_optimization(
                        resource_name="agem-demo-service",
                        resource_type="cloud_run",
                        cws_before=waste,
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
    
    return jsonify({
        "project": PROJECT_ID,
        "resources_scanned": len(resources),
        "patches_approved": approved,
        "resources_skipped": skipped,
        "total_estimated_monthly_savings": savings["total_estimated_monthly_savings"],
        "total_optimizations_in_history": savings["total_optimizations"],
        "scan_duration_sec": round(time.time() - start, 2),
        "results": results,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
