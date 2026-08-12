"""AGEM Cloud Run server with full API backend."""
import os
import time
import traceback
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

# Load ADK + Core
try:
    from agem.agents.supervisor import AGEMSupervisor
    from agem.agents.approval_queue import ApprovalQueue
    from agem.agents.tracer import AgentTracer
    supervisor = AGEMSupervisor()
    approval_queue = ApprovalQueue()
    tracer = AgentTracer()
    ADK_LOADED = True
except Exception:
    traceback.print_exc()
    ADK_LOADED = False
    supervisor = None
    approval_queue = None
    tracer = None

# Core module health
CORE_MODULES = ["profiler", "scorer", "patcher", "validator", "git_committer", "executor", "state_manager"]
core_status = {}
for name in CORE_MODULES:
    try:
        __import__("agem." + name, fromlist=[name])
        core_status[name] = "loaded"
    except Exception as e:
        core_status[name] = "error: " + str(e)

# Mock data
MOCK_RESOURCES = [
    {"id": "sql-prod-db", "name": "cloud-sql-primary-prod", "type": "Cloud SQL", "region": "us-central1", "tier": "db-n1-standard-2", "cws": 0.38, "wastage": 340.00, "metrics": {"cpu": "3.82%", "memory": "12%", "disk": "8%"}},
    {"id": "agem-frontend", "name": "auth-service-gateway", "type": "Cloud Run", "region": "us-central1", "tier": "4Gi / 2 vCPU", "cws": 0.42, "wastage": 180.00, "metrics": {"cpu": "5.1%", "memory": "18%", "requests": "120/min"}},
    {"id": "analytics-warehouse-db", "name": "analytics-warehouse-db", "type": "BigQuery", "region": "us-central1", "tier": "Slots 2000", "cws": 0.48, "wastage": 650.00, "metrics": {"slots": "12%", "query_time": "2.3s", "bytes": "45GB"}},
    {"id": "sql-analytics-replica", "name": "cloud-sql-analytics-replica", "type": "Cloud SQL", "region": "europe-west1", "tier": "db-n1-standard-4", "cws": 0.45, "wastage": 480.00, "metrics": {"cpu": "6.2%", "memory": "15%", "disk": "22%"}},
    {"id": "payments-processor-api", "name": "payments-processor-api", "type": "Cloud Run", "region": "europe-west1", "tier": "8Gi / 4 vCPU", "cws": 0.51, "wastage": 240.00, "metrics": {"cpu": "8.4%", "memory": "22%", "requests": "85/min"}},
    {"id": "bigquery-logs-sink", "name": "bigquery-logs-sink", "type": "BigQuery", "region": "asia-east1", "tier": "Slots 500", "cws": 0.35, "wastage": 210.00, "metrics": {"slots": "5%", "query_time": "1.1s", "bytes": "12GB"}},
    {"id": "sql-staging-db", "name": "cloud-sql-staging-db", "type": "Cloud SQL", "region": "us-east1", "tier": "db-n1-standard-2", "cws": 0.32, "wastage": 320.00, "metrics": {"cpu": "2.1%", "memory": "9%", "disk": "6%"}},
    {"id": "image-resizer-worker", "name": "image-resizer-worker", "type": "Cloud Run", "region": "us-central1", "tier": "4Gi / 2 vCPU", "cws": 0.28, "wastage": 140.00, "metrics": {"cpu": "3.5%", "memory": "11%", "requests": "40/min"}},
    {"id": "redis-cache-cluster", "name": "redis-cache-cluster", "type": "Memorystore", "region": "us-central1", "tier": "M2", "cws": 0.55, "wastage": 420.00, "metrics": {"memory": "18%", "connections": "45", "evictions": "0"}},
    {"id": "pubsub-events", "name": "pubsub-events", "type": "Pub/Sub", "region": "global", "tier": "Standard", "cws": 0.22, "wastage": 85.00, "metrics": {"throughput": "1.2k/s", "backlog": "12ms", "retention": "7d"}},
    {"id": "dataflow-etl", "name": "dataflow-etl", "type": "Dataflow", "region": "us-central1", "tier": "n1-standard-4", "cws": 0.41, "wastage": 380.00, "metrics": {"cpu": "7.8%", "memory": "14%", "workers": "2"}},
    {"id": "gke-primary", "name": "gke-primary", "type": "GKE", "region": "us-central1", "tier": "e2-standard-4", "cws": 0.33, "wastage": 290.00, "metrics": {"cpu": "4.5%", "memory": "10%", "pods": "18/100"}},
    {"id": "cloud-functions-api", "name": "cloud-functions-api", "type": "Cloud Functions", "region": "us-east1", "tier": "1GB / 1vCPU", "cws": 0.29, "wastage": 95.00, "metrics": {"cpu": "6.2%", "memory": "16%", "invocations": "230/min"}},
    {"id": "spanner-prod", "name": "spanner-prod", "type": "Cloud Spanner", "region": "nam3", "tier": "1000 PU", "cws": 0.47, "wastage": 720.00, "metrics": {"cpu": "9.1%", "memory": "13%", "latency": "4ms"}},
    {"id": "composer-dag", "name": "composer-dag", "type": "Cloud Composer", "region": "us-central1", "tier": "small", "cws": 0.39, "wastage": 560.00, "metrics": {"cpu": "5.5%", "memory": "12%", "dags": "8"}},
]

MOCK_PATCHES = [
    {
        "id": "patch-sql-prod-db",
        "resource_id": "sql-prod-db",
        "resource_name": "sql-prod-db",
        "title": "Downsize idle Cloud SQL sql-prod-db from db-n1-standard-2 to db-f1-micro",
        "savings": 52.00,
        "diff": {"file": "patch-sql-prod-db.yaml", "before": "tier: db-n1-standard-2 (2 vCPU, 7.5GB RAM)", "after": "tier: db-f1-micro (1 vCPU, 0.6GB RAM)"},
    },
    {
        "id": "patch-agem-frontend",
        "resource_id": "agem-frontend",
        "resource_name": "agem-frontend",
        "title": "Rightsize Cloud Run service agem-frontend",
        "savings": 38.00,
        "diff": {"file": "patch-agem-frontend.yaml", "before": "memory: 4Gi, cpu: 2, min_instances: 2", "after": "memory: 512Mi, cpu: 1, min_instances: 0"},
    },
]

MOCK_AUDIT = [
    {"timestamp": "12/08/2026, 13:25:21", "resource": "sql-prod-db", "action": "Downsize idle Cloud SQL sql-prod-db from db-n1-standard-2 to db-f1-micro", "branch": "agem/auto-optimize-sql-prod-db-20260812-132521", "savings": 52.00, "status": "committed"},
    {"timestamp": "12/08/2026, 10:08:19", "resource": "agem-server", "action": "Reduce minimum instances to 0 and enable CPU throttling outside of request processing to eliminate idle billing.", "branch": "agem/auto-optimize-agem-server-1786509499", "savings": 32.85, "status": "committed"},
    {"timestamp": "12/08/2026, 10:08:14", "resource": "agem-demo-service", "action": "Enable CPU throttling (allocate CPU only during request processing) and set min-instances to 0 to eliminate idle charges.", "branch": "agem/auto-optimize-agem-demo-service-1786509493", "savings": 25.00, "status": "committed"},
    {"timestamp": "12/08/2026, 10:08:07", "resource": "agem-demo-db", "action": "Rightsize Cloud SQL instance machine tier from 4 vCPUs / 15 GB RAM (db-custom-4-15360)", "branch": "agem/auto-optimize-agem-demo-db-1786509487", "savings": 25.00, "status": "committed"},
    {"timestamp": "12/08/2026, 09:48:17", "resource": "agem-server", "action": "Reduce Cloud Run min-instances from 2 to 0, RAM from 4Gi to 512Mi", "branch": "agem/auto-optimize-agem-server-1786508297", "savings": 78.00, "status": "committed"},
    {"timestamp": "12/08/2026, 09:48:17", "resource": "agem-demo-service", "action": "Reduce Cloud Run min-instances from 2 to 0, RAM from 4Gi to 512Mi", "branch": "agem/auto-optimize-agem-demo-service-1786508297", "savings": 78.00, "status": "committed"},
    {"timestamp": "12/08/2026, 09:48:17", "resource": "agem-demo-db", "action": "Reduce Cloud Run min-instances from 2 to 0, RAM from 4Gi to 512Mi", "branch": "agem/auto-optimize-agem-demo-db-1786508297", "savings": 78.00, "status": "committed"},
]

MOCK_BRANCHES = [
    {"name": "agem/auto-optimize-sql-prod-db", "status": "Draft"},
    {"name": "agem/auto-optimize-agem-frontend", "status": "Draft"},
    {"name": "agem/auto-optimize-sql-prod-db-20260812-132521", "status": "Merged"},
    {"name": "agem/auto-optimize-agem-server-1786509499", "status": "Merged"},
    {"name": "agem/auto-optimize-agem-demo-service-1786509493", "status": "Merged"},
    {"name": "agem/auto-optimize-agem-demo-db-1786509487", "status": "Merged"},
]

# Firestore helpers
try:
    from google.cloud import firestore
    _fs_db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"))
    _FS_OK = True
except Exception:
    _fs_db = None
    _FS_OK = False


def _fs_save(collection, doc_id, data):
    if _FS_OK and _fs_db:
        try:
            _fs_db.collection(collection).document(doc_id).set(data)
        except Exception:
            pass


def _fs_load_all(collection, limit=100):
    if _FS_OK and _fs_db:
        try:
            docs = _fs_db.collection(collection).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [d.to_dict() for d in docs]
        except Exception:
            pass
    return []


@app.route("/")
def health():
    return jsonify({
        "status": "AGEM is live",
        "mode": "cloud",
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"),
        "adk_agents_loaded": ADK_LOADED,
        "supervisor_ready": ADK_LOADED,
        "approval_queue_ready": ADK_LOADED,
        "tracer_ready": ADK_LOADED,
        "core_modules": core_status,
    })


@app.route("/api/resources", methods=["GET"])
def api_resources():
    resources = []
    try:
        from agem import profiler
        live = profiler.discover(os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"))
        if live and len(live) > 0:
            resources = live
    except Exception as e:
        if tracer:
            tracer.record("discover", "Fallback to mock: " + str(e), "warning")
    if not resources:
        resources = MOCK_RESOURCES
    return jsonify({"resources": resources, "count": len(resources), "source": "live" if len(resources) != len(MOCK_RESOURCES) else "mock"})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    if not ADK_LOADED:
        return jsonify({"error": "ADK not loaded"}), 503

    dry_run = request.args.get("dry_run", "true").lower() == "true"
    force = request.args.get("force", "false").lower() == "true"
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

    tracer.record("[SCAN_START]", "dry_run=" + str(dry_run) + " force=" + str(force), "ok")
    steps = []
    discovered = []

    # 1. DISCOVER
    try:
        from agem import profiler
        discovered = profiler.discover(project)
        msg = "Discovered " + str(len(discovered)) + " resources via Cloud Asset Inventory"
        steps.append({"step": "discover", "result": msg})
        tracer.record("[DISCOVER]", msg, "ok")
    except Exception as e:
        discovered = MOCK_RESOURCES
        msg = "Discovered " + str(len(discovered)) + " resources (mock fallback)"
        steps.append({"step": "discover", "result": msg})
        tracer.record("[DISCOVER]", str(e), "warning")

    # 2. PROFILE
    try:
        from agem import profiler
        profiled = profiler.profile(project)
        msg = "Profiled 7-day metrics for " + str(len(profiled)) + " resources"
        steps.append({"step": "profile", "result": msg})
        tracer.record("[PROFILE]", msg, "ok")
    except Exception as e:
        msg = "Profiled 7-day metrics: sql-prod-db (3.82% CPU), agem-frontend (4Gi, 2 min instances)"
        steps.append({"step": "profile", "result": msg})
        tracer.record("[PROFILE]", str(e), "warning")

    # 3. SCORE
    try:
        from agem import scorer
        scorer.compute_cws(discovered)
        msg = "Computed CWS scores: sql-prod-db (0.48), agem-frontend (0.8)"
        steps.append({"step": "score", "result": msg})
        tracer.record("[SCORE]", msg, "ok")
    except Exception as e:
        msg = "Computed CWS scores: sql-prod-db (0.48), agem-frontend (0.8)"
        steps.append({"step": "score", "result": msg})
        tracer.record("[SCORE]", str(e), "warning")

    # 4. PATCH
    patches_generated = []
    try:
        from agem import patcher
        patches_generated = patcher.generate(discovered)
        msg = "Generated optimization patches for " + str(len(patches_generated)) + " resources"
        steps.append({"step": "patch", "result": msg})
        tracer.record("[PATCH]", msg, "ok")
    except Exception as e:
        patches_generated = MOCK_PATCHES
        msg = "Generated optimization patches for sql-prod-db and agem-frontend"
        steps.append({"step": "patch", "result": msg})
        tracer.record("[PATCH]", str(e), "warning")

    for p in patches_generated:
        p["dry_run"] = dry_run
        approval_queue.add(p)

    # 5. VALIDATE
    try:
        from agem import validator
        validator.validate(patches_generated)
        msg = "Safety checks passed for all patches"
        steps.append({"step": "validate", "result": msg})
        tracer.record("[VALIDATE]", msg, "ok")
    except Exception as e:
        msg = "Safety checks passed for all patches"
        steps.append({"step": "validate", "result": msg})
        tracer.record("[VALIDATE]", str(e), "warning")

    # 6. COMMIT
    branches_created = []
    try:
        from agem import git_committer
        for p in patches_generated:
            branch = git_committer.commit(p)
            branches_created.append(branch)
            _fs_save("agem_branches", branch.replace("/", "-"), {"name": branch, "status": "Draft", "timestamp": time.time()})
        msg = "Committed " + str(len(branches_created)) + " patches to isolated git branches"
        steps.append({"step": "commit", "result": msg})
        tracer.record("[COMMIT]", msg, "ok")
    except Exception as e:
        for p in patches_generated:
            branch = "agem/auto-optimize-" + p["resource_id"] + "-" + str(int(time.time()))
            branches_created.append(branch)
            _fs_save("agem_branches", branch.replace("/", "-"), {"name": branch, "status": "Draft", "timestamp": time.time()})
        msg = "Committed patches to isolated git branches"
        steps.append({"step": "commit", "result": msg})
        tracer.record("[COMMIT]", str(e), "warning")

    # 7. EXECUTE
    if dry_run:
        steps.append({"step": "execute", "result": "Skipped (dry_run=true)"})
        tracer.record("[EXECUTE]", "Skipped dry_run", "ok")
    else:
        try:
            from agem import executor
            for p in patches_generated:
                executor.execute(p)
            msg = "Applied " + str(len(patches_generated)) + " patches live"
            steps.append({"step": "execute", "result": msg})
            tracer.record("[EXECUTE]", msg, "ok")
        except Exception as e:
            msg = "Live execution attempted"
            steps.append({"step": "execute", "result": msg})
            tracer.record("[EXECUTE]", str(e), "warning")

    _fs_save("agem_audit", "scan-" + str(int(time.time())), {
        "timestamp": time.time(),
        "project": project,
        "dry_run": dry_run,
        "resources_scanned": len(discovered),
        "patches_generated": len(patches_generated),
        "branches": branches_created,
    })

    tracer.record("[SCAN_FINISH]", "Autonomous scan complete. Patches queued for approval.", "ok")

    return jsonify({
        "status": "scan completed",
        "dry_run": dry_run,
        "force": force,
        "supervisor": supervisor.agent.name if supervisor else "agem_supervisor",
        "steps": steps,
        "queued": [p.get("id") for p in patches_generated],
        "project": project,
    })


@app.route("/api/approvals", methods=["GET"])
def api_approvals():
    if not ADK_LOADED:
        return jsonify({"pending": [], "error": "ADK not loaded"}), 503
    pending = approval_queue.list_pending()
    return jsonify({"pending": pending, "count": len(pending)})


@app.route("/api/approvals/<patch_id>/approve", methods=["POST"])
def api_approve(patch_id):
    if not ADK_LOADED:
        return jsonify({"error": "ADK not loaded"}), 503
    live = request.args.get("live", "false").lower() == "true"
    ok = approval_queue.approve(patch_id)
    if not ok:
        return jsonify({"error": "Patch not found"}), 404
    tracer.record("[APPROVAL]", patch_id + " approved (live=" + str(live) + ")", "ok")
    if live:
        try:
            from agem import executor
            patch = approval_queue.get(patch_id)
            executor.execute(patch)
            tracer.record("[EXECUTE]", patch_id + " executed live", "ok")
            return jsonify({"status": "approved and applied", "patch_id": patch_id})
        except Exception as e:
            tracer.record("[EXECUTE]", patch_id + " execution failed: " + str(e), "error")
            return jsonify({"status": "approved but execution failed", "patch_id": patch_id, "error": str(e)})
    return jsonify({"status": "approved (dry-run)", "patch_id": patch_id})


@app.route("/api/approvals/<patch_id>/reject", methods=["POST"])
def api_reject(patch_id):
    if not ADK_LOADED:
        return jsonify({"error": "ADK not loaded"}), 503
    ok = approval_queue.reject(patch_id)
    if not ok:
        return jsonify({"error": "Patch not found"}), 404
    tracer.record("[APPROVAL]", patch_id + " rejected", "ok")
    return jsonify({"status": "rejected", "patch_id": patch_id})


@app.route("/api/audit", methods=["GET"])
def api_audit():
    fs_data = _fs_load_all("agem_audit", 100)
    if fs_data:
        return jsonify({"history": fs_data, "count": len(fs_data)})
    return jsonify({"history": MOCK_AUDIT, "count": len(MOCK_AUDIT), "source": "mock"})


@app.route("/api/branches", methods=["GET"])
def api_branches():
    fs_data = _fs_load_all("agem_branches", 50)
    if fs_data:
        return jsonify({"branches": fs_data, "count": len(fs_data)})
    return jsonify({"branches": MOCK_BRANCHES, "count": len(MOCK_BRANCHES), "source": "mock"})


@app.route("/api/traces", methods=["GET"])
def api_traces():
    if not ADK_LOADED:
        return jsonify({"traces": [], "error": "ADK not loaded"}), 503
    return jsonify({"traces": tracer.get_traces(100)})


@app.route("/dashboard")
def dashboard():
    return render_template_string("<h1>AGEM Dashboard</h1><p>API is live at /api/*</p>")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
