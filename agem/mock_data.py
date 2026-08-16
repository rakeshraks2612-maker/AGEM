"""Centralized mock and baseline datasets for AGEM."""

MOCK_RESOURCES = [
    {
        "id": "agem-demo-db",
        "name": "projects/agem-505107/instances/agem-demo-db",
        "type": "Cloud SQL",
        "tier": "db-n1-standard-2",
        "region": "us-central1",
        "cws": 0.46,
        "wastage": 52.00,
        "metrics": {
            "cpu_utilization_7d_avg": 0.0428,
            "cpu": "4.3%",
            "memory": "1.2 GB / 7.5 GB",
            "disk_io": "12 IOPS",
            "has_public_ip": False,
            "automated_backups": True,
            "ssl_enforced": True,
            "multi_zone": False
        },
        "cws_detail": {
            "total": 0.46,
            "cost_score": 0.90,
            "perf_score": 0.15,
            "sec_score": 0.20,
            "rel_score": 0.35,
            "dominant_bottleneck": "Cost (Over-provisioned vCPU)",
            "recommendation": "Downsize db-n1-standard-2 to db-f1-micro for dev/idle workloads"
        }
    },
    {
        "id": "agem-demo-service",
        "name": "projects/agem-505107/locations/us-central1/services/agem-demo-service",
        "type": "Cloud Run",
        "tier": "2 vCPU, 4Gi RAM",
        "region": "us-central1",
        "cws": 0.80,
        "wastage": 72.00,
        "metrics": {
            "memory_limit_gi": 4,
            "min_instances": 2,
            "max_instances": 10,
            "concurrency": 80,
            "cpu": "1.8%",
            "memory_p99_mi": 256,
            "cold_starts_daily": 0,
            "ingress": "all"
        },
        "cws_detail": {
            "total": 0.80,
            "cost_score": 0.95,
            "perf_score": 0.85,
            "sec_score": 0.10,
            "rel_score": 0.10,
            "dominant_bottleneck": "Cost (Idle Min Instances & RAM)",
            "recommendation": "Scale min-instances 2 -> 0, reduce RAM 4Gi -> 512Mi"
        }
    },
    {
        "id": "bigquery-analytics-core",
        "name": "projects/agem-505107/datasets/analytics_core",
        "type": "BigQuery",
        "tier": "On-Demand Slot Allocation",
        "region": "us-central1",
        "cws": 0.65,
        "wastage": 45.00,
        "metrics": {
            "slots_utilization": 0.12,
            "unpartitioned_gb": 45.0,
            "has_expiration": False,
            "total_tables": 24,
            "monthly_bytes_billed_tb": 12.5
        },
        "cws_detail": {
            "total": 0.65,
            "cost_score": 0.70,
            "perf_score": 0.60,
            "sec_score": 0.10,
            "rel_score": 0.20,
            "dominant_bottleneck": "Cost (Unpartitioned Tables & On-Demand Slots)",
            "recommendation": "Partition tables by date and set 90-day partition expiration"
        }
    },
    {
        "id": "agem-server",
        "name": "projects/agem-505107/locations/us-central1/services/agem-server",
        "type": "Cloud Run",
        "tier": "1 vCPU, 1Gi RAM",
        "region": "us-central1",
        "cws": 0.15,
        "wastage": 0.00,
        "metrics": {
            "memory_limit_gi": 1,
            "min_instances": 0,
            "max_instances": 10,
            "concurrency": 80,
            "cpu": "12.4%",
            "memory_p99_mi": 380,
            "ingress": "all"
        },
        "cws_detail": {
            "total": 0.15,
            "cost_score": 0.10,
            "perf_score": 0.15,
            "sec_score": 0.05,
            "rel_score": 0.05,
            "dominant_bottleneck": "None (Healthy)",
            "recommendation": "Maintain current right-sized configuration"
        }
    },
    {
        "id": "redis-session-cache",
        "name": "projects/agem-505107/locations/us-central1/instances/redis-session-cache",
        "type": "Memorystore",
        "tier": "Basic Tier (5 GB)",
        "region": "us-central1",
        "cws": 0.55,
        "wastage": 34.00,
        "metrics": {
            "memory_usage_ratio": 0.08,
            "cpu_utilization": 0.02,
            "network_egress_mb": 420
        },
        "cws_detail": {
            "total": 0.55,
            "cost_score": 0.65,
            "perf_score": 0.10,
            "sec_score": 0.10,
            "rel_score": 0.30,
            "dominant_bottleneck": "Cost (Memory Headroom 92% Idle)",
            "recommendation": "Downsize cache instance capacity from 5GB to 1GB"
        }
    }
]

MOCK_BRANCHES = [
    {
        "branch": "agem/auto-optimize-agem-demo-service-20260815-180000",
        "resource": "agem-demo-service",
        "savings": "$72.00/mo",
        "status": "committed",
        "timestamp": "2026-08-15T18:00:00Z"
    },
    {
        "branch": "agem/auto-optimize-agem-demo-db-20260815-180500",
        "resource": "agem-demo-db",
        "savings": "$52.00/mo",
        "status": "committed",
        "timestamp": "2026-08-15T18:05:00Z"
    },
    {
        "branch": "agem/auto-optimize-bigquery-analytics-core-20260815-181000",
        "resource": "bigquery-analytics-core",
        "savings": "$45.00/mo",
        "status": "committed",
        "timestamp": "2026-08-15T18:10:00Z"
    }
]
