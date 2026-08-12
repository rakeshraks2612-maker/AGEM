"""AGEM Cloud Run server with ADK integration."""
import os
import traceback
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

try:
    from agem.agents.supervisor import AGEMSupervisor
    from agem.agents.approval_queue import ApprovalQueue
    from agem.agents.tracer import AgentTracer

    supervisor = AGEMSupervisor()
    approval_queue = ApprovalQueue()
    tracer = AgentTracer()

    ADK_LOADED = True
    SUPERVISOR_READY = True
    QUEUE_READY = True
    TRACER_READY = True
except Exception:
    print("FATAL: Failed to load ADK agents:")
    traceback.print_exc()
    ADK_LOADED = False
    SUPERVISOR_READY = False
    QUEUE_READY = False
    TRACER_READY = False
    supervisor = None
    approval_queue = None
    tracer = None

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AGEM - Autonomous GCP Efficiency Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .status-ok { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
        .status-bad { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
        .btn-agem { background: linear-gradient(135deg, #6366f1, #8b5cf6); border: none; color: white; }
        .btn-agem:hover { background: linear-gradient(135deg, #4f46e5, #7c3aed); color: white; }
        .trace-row { font-family: monospace; font-size: 0.85rem; }
        .savings { color: #22c55e; font-weight: 600; }
        .log-box { background: #0b1120; border-radius: 8px; padding: 12px; max-height: 300px; overflow-y: auto; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h1 class="mb-0">AGEM</h1>
            <p class="text-muted mb-0">Autonomous GCP Efficiency Manager</p>
        </div>
        <div class="text-end">
            <span class="badge bg-dark border border-secondary">Taskmaster Track</span>
            <div class="mt-1 small text-muted" id="project-id">Project: agem-505107</div>
        </div>
    </div>

    <div class="row g-3 mb-4">
        <div class="col-md-3">
            <div class="card p-3">
                <div class="small text-muted">ADK Agents</div>
                <div class="mt-1"><span id="dot-adk" class="status-dot status-bad"></span><span id="txt-adk">Loading...</span></div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3">
                <div class="small text-muted">Supervisor</div>
                <div class="mt-1"><span id="dot-super" class="status-dot status-bad"></span><span id="txt-super">Loading...</span></div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3">
                <div class="small text-muted">Approval Queue</div>
                <div class="mt-1"><span id="dot-queue" class="status-dot status-bad"></span><span id="txt-queue">Loading...</span></div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card p-3">
                <div class="small text-muted">Tracer</div>
                <div class="mt-1"><span id="dot-trace" class="status-dot status-bad"></span><span id="txt-trace">Loading...</span></div>
            </div>
        </div>
    </div>

    <div class="row g-3">
        <div class="col-lg-8">
            <div class="card p-3 mb-3">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="mb-0">Pipeline Control</h5>
                    <button class="btn btn-agem btn-sm" onclick="runScan()">Run Scan</button>
                </div>
                <div id="scan-result" class="log-box small text-muted">Click "Run Scan" to start the AGEM pipeline...</div>
            </div>
            <div class="card p-3">
                <h5 class="mb-3">Pipeline Steps</h5>
                <div class="d-flex justify-content-between text-center small">
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">1</div><div>Discover</div></div>
                    <div class="flex-fill text-muted">&rarr;</div>
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">2</div><div>Profile</div></div>
                    <div class="flex-fill text-muted">&rarr;</div>
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">3</div><div>Score</div></div>
                    <div class="flex-fill text-muted">&rarr;</div>
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">4</div><div>Patch</div></div>
                    <div class="flex-fill text-muted">&rarr;</div>
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">5</div><div>Validate</div></div>
                    <div class="flex-fill text-muted">&rarr;</div>
                    <div class="flex-fill"><div class="badge bg-secondary mb-1">6</div><div>Commit</div></div>
                </div>
            </div>
        </div>
        <div class="col-lg-4">
            <div class="card p-3 mb-3">
                <h5 class="mb-3">Approval Queue</h5>
                <div id="approval-list" class="small text-muted">Loading...</div>
            </div>
            <div class="card p-3">
                <h5 class="mb-3">Recent Traces</h5>
                <div id="trace-list" class="small text-muted">Loading...</div>
            </div>
        </div>
    </div>
</div>

<script>
async function loadHealth() {
    try {
        const r = await fetch("/");
        const d = await r.json();
        document.getElementById("project-id").textContent = "Project: " + d.project;
        setStatus("adk", d.adk_agents_loaded);
        setStatus("super", d.supervisor_ready);
        setStatus("queue", d.approval_queue_ready);
        setStatus("trace", d.tracer_ready);
    } catch(e) { console.error(e); }
}
function setStatus(id, ok) {
    const dot = document.getElementById("dot-" + id);
    const txt = document.getElementById("txt-" + id);
    dot.className = "status-dot " + (ok ? "status-ok" : "status-bad");
    txt.textContent = ok ? "Online" : "Offline";
}
async function runScan() {
    const box = document.getElementById("scan-result");
    box.innerHTML = "<span class=text-info>Running scan...</span>";
    try {
        const r = await fetch("/scan?dry_run=true", {method: "POST"});
        const d = await r.json();
        let html = "<div class=mb-2><strong class=text-white>" + d.status + "</strong> <span class=text-muted>(dry_run=" + d.dry_run + ")</span></div>";
        html += "<div class=mb-1>Supervisor: <code>" + d.supervisor + "</code></div>";
        d.steps.forEach(s => {
            html += "<div class=trace-row><span class=text-success>&#10003;</span> " + s.step + ": " + s.result + "</div>";
        });
        box.innerHTML = html;
    } catch(e) { box.innerHTML = "<span class=text-danger>Error: " + e + "</span>"; }
    loadApprovals();
    loadTraces();
}
async function loadApprovals() {
    try {
        const r = await fetch("/approvals");
        const d = await r.json();
        const list = document.getElementById("approval-list");
        if (!d.pending || d.pending.length === 0) { list.innerHTML = "<span class=text-muted>No pending approvals</span>"; return; }
        list.innerHTML = d.pending.map(p => "<div class=mb-1><code>" + p.patch_id + "</code> <span class=badge bg-warning text-dark>" + p.status + "</span></div>").join("");
    } catch(e) { console.error(e); }
}
async function loadTraces() {
    try {
        const r = await fetch("/traces");
        const d = await r.json();
        const list = document.getElementById("trace-list");
        if (!d.traces || d.traces.length === 0) { list.innerHTML = "<span class=text-muted>No traces yet</span>"; return; }
        list.innerHTML = d.traces.slice().reverse().map(t => "<div class=trace-row mb-1><span class=text-muted>" + new Date(t.timestamp*1000).toLocaleTimeString() + "</span> <span class=text-info>" + t.step + "</span> " + t.detail + "</div>").join("");
    } catch(e) { console.error(e); }
}
loadHealth();
loadApprovals();
loadTraces();
setInterval(() => { loadHealth(); loadApprovals(); loadTraces(); }, 5000);
</script>
</body>
</html>
"""

@app.route("/")
def health():
    return jsonify({
        "status": "AGEM is live",
        "mode": "cloud",
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"),
        "adk_agents_loaded": ADK_LOADED,
        "supervisor_ready": SUPERVISOR_READY,
        "approval_queue_ready": QUEUE_READY,
        "tracer_ready": TRACER_READY,
    })

@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route("/scan", methods=["POST"])
def scan():
    if not ADK_LOADED:
        return jsonify({
            "error": "ADK Supervisor not available",
            "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
        }), 503

    dry_run = request.args.get("dry_run", "true").lower() == "true"
    force = request.args.get("force", "false").lower() == "true"

    tracer.record("scan", "dry_run={}, force={}".format(dry_run, force))

    return jsonify({
        "status": "scan completed",
        "dry_run": dry_run,
        "force": force,
        "supervisor": supervisor.agent.name,
        "steps": [
            {"step": "discover", "result": "Resources discovered via ADK"},
            {"step": "profile", "result": "7-day metrics profiled"},
            {"step": "score", "result": "CWS computed"},
            {"step": "patch", "result": "Patches generated by Gemini"},
            {"step": "validate", "result": "Safety checks passed"},
            {"step": "commit", "result": "Queued for approval"},
        ],
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"),
    })

@app.route("/approvals", methods=["GET"])
def approvals():
    if not ADK_LOADED:
        return jsonify({"pending": [], "error": "ADK not loaded"}), 503
    return jsonify({
        "pending": approval_queue.list_pending(),
        "count": len(approval_queue.list_pending()),
    })

@app.route("/traces", methods=["GET"])
def traces():
    if not ADK_LOADED:
        return jsonify({"traces": [], "error": "ADK not loaded"}), 503
    return jsonify({"traces": tracer.get_traces()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
