# agem/profiler.py
import os
import time
from typing import List, Dict, Any
from google.cloud import asset_v1, monitoring_v3
from google.protobuf import duration_pb2

PROJECT_ID = "agem-505107"


def discover_resources() -> List[Dict[str, Any]]:
    """List compute resources via Cloud Asset Inventory API."""
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
    """Fetch 7-day average CPU utilization for a Cloud SQL instance."""
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{PROJECT_ID}"
    
    now = time.time()
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(now)},
        "start_time": {"seconds": int(now - (days * 86400))},
    })
    
    # Cloud SQL CPU metric filter
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


if __name__ == "__main__":
    print(f"[AGEM] Discovering resources in project: {PROJECT_ID}")
    resources = discover_resources()
    print(f"[AGEM] Found {len(resources)} resources")
    
    for r in resources:
        print(f"  - {r['type']}: {r['name']}")
        if "sqladmin" in r['type']:
            # Extract instance name from full resource path
            instance_name = r['name'].split('/')[-1]
            cpu = get_cloud_sql_cpu(instance_name)
            print(f"    CPU (7d avg): {cpu * 100:.2f}%")
