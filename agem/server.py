import os
import json
import traceback
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

RUNNING_IN_CLOUD = os.environ.get("K_SERVICE") is not None
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

# ── Import AGEM Multi-Agent System ───────────────────────────
try:
    from agem.agents.supervisor import AGEMSupervisor
    from agem.agents.approval_queue import ApprovalQueue
    from agem.agents.tracer import AgentTracer
    ADK_AGENTS_AVAILABLE = True
except Exception as e:
    ADK_AGENTS_AVAILABLE = False
    AGEMSupervisor = None
    ApprovalQueue = None
    AgentTracer = None

# Initialize singletons
supervisor = AGEMSupervisor() if ADK_AGENTS_AVAILABLE else None
approval_queue = ApprovalQueue() if ADK_AGENTS_AVAILABLE else None
tracer = AgentTracer() if ADK_AGENTS_AVAILABLE else None

# ── Routes ───────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "project": PROJECT_ID,
        "status": "AGEM is live",
        "mode": "cloud" if RUNNING_IN_CLOUD else "local",
        "adk_agents_loaded": ADK_AGENTS_AVAILABLE,
        "supervisor_ready": supervisor is not None,
        "approval_queue_ready": approval_queue is not None,
        "tracer_ready": tracer is not None,
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "project": PROJECT_ID})

@app.route("/scan", methods=["POST"])
def scan():
    \"\"\"Run the full AGEM pipeline via ADK Supervisor agent.\"\"\"
    if supervisor is None:
        return jsonify({"error": "ADK Supervisor not available", "project": PROJECT_ID}), 503
    
    force = request.args.get("force", "false").lower() == "true"
    dry_run = request.args.get("dry_run", "true" if RUNNING_IN_CLOUD else "false").lower() == "true"
    
    try:
        result = supervisor.run_pipeline(force=force, dry_run=dry_run)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "project": PROJECT_ID,
        }), 500

@app.route("/approvals", methods=["GET"])
def list_approvals():
    \"\"\"List pending human approvals.\"\"\"
    if approval_queue is None:
        return jsonify({"error": "Approval queue not available"}), 503
    try:
        pending = approval_queue.list_pending()
        stats = approval_queue.get_stats()
        return jsonify({
            "project": PROJECT_ID,
            "pending": pending,
            "stats": stats,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/approvals/<approval_id>/approve", methods=["POST"])
def approve_patch(approval_id):
    \"\"\"Human approves a pending patch.\"\"\"
    if approval_queue is None:
        return jsonify({"error": "Approval queue not available"}), 503
    try:
        success = approval_queue.approve(approval_id, approved_by="human")
        if success:
            return jsonify({"success": True, "approval_id": approval_id, "status": "approved"})
        return jsonify({"success": False, "approval_id": approval_id, "error": "Approval not found or already processed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/approvals/<approval_id>/reject", methods=["POST"])
def reject_patch(approval_id):
    \"\"\"Human rejects a pending patch.\"\"\"
    if approval_queue is None:
        return jsonify({"error": "Approval queue not available"}), 503
    try:
        reason = request.json.get("reason", "") if request.is_json else ""
        success = approval_queue.reject(approval_id, reason=reason)
        if success:
            return jsonify({"success": True, "approval_id": approval_id, "status": "rejected"})
        return jsonify({"success": False, "approval_id": approval_id, "error": "Approval not found or already processed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/traces", methods=["GET"])
def list_traces():
    \"\"\"List agent execution traces.\"\"\"
    if tracer is None:
        return jsonify({"error": "Tracer not available"}), 503
    try:
        traces = tracer.list_traces(limit=50)
        return jsonify({
            "project": PROJECT_ID,
            "count": len(traces),
            "traces": traces,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/traces/<trace_id>", methods=["GET"])
def get_trace(trace_id):
    \"\"\"Get a single trace by ID.\"\"\"
    if tracer is None:
        return jsonify({"error": "Tracer not available"}), 503
    try:
        trace = tracer.get_trace(trace_id)
        if trace:
            return jsonify({"project": PROJECT_ID, "trace": trace})
        return jsonify({"error": "Trace not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["GET"])
def history():
    \"\"\"Legacy endpoint — optimization history from Firestore.\"\"\"
    try:
        from agem.state_manager import StateManager
        state = StateManager()
        savings = state.get_total_estimated_savings()
        return jsonify({
            "project": PROJECT_ID,
            "total_estimated_monthly_savings": savings.get("total_estimated_monthly_savings", 0),
            "total_optimizations": savings.get("total_optimizations", 0),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/dashboard")
def dashboard():
    \"\"\"Interactive HTML dashboard for judges.\"\"\"
    html = \"\"\"<!DOCTYPE html>
<html><head><title>AGEM Dashboard</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1000px;margin:40px auto;padding:20px;background:#0f0f23;color:#e0e0e0}
h1{color:#00ff88;border-bottom:2px solid #00ff88;padding-bottom:10px}
.card{background:#1a1a2e;border-radius:12px;padding:20px;margin:16px 0;border:1px solid #2a2a4e}
.metric{font-size:2em;font-weight:bold;color:#00ff88}
.label{color:#888;font-size:.9em;text-transform:uppercase;letter-spacing:1px}
button{background:#00ff88;color:#0f0f23;border:none;padding:12px 24px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:1em;margin-right:10px}
button.secondary{background:#2a2a4e;color:#fff}
button.danger{background:#ff4444;color:#fff}
button:hover{opacity:.9}
pre{background:#0a0a1a;padding:16px;border-radius:8px;overflow-x:auto;font-size:.85em}
.status-ok{color:#00ff88}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75em;margin-right:4px}
.tag-ok{background:#004d1a;color:#00ff88}
.tag-err{background:#4d0000;color:#ff4444}
.tag-warn{background:#4d3a00;color:#ffaa00}
.approval-card{background:#1a1a2e;border:1px solid #2a2a4e;border-radius:8px;padding:12px;margin:8px 0}
.approval-card button{margin-top:8px}
</style></head>
<body>
<h1>🔧 AGEM — Autonomous Google-powered Efficiency Manager</h1>
<div class="card">
<p class="label">Project</p><p style="font-size:1.2em">{{ project }}</p>
<p class="label">Status</p><p class="status-ok">● Live on Google Cloud Run</p>
<p class="label">Architecture</p>
<p><span class="tag tag-ok">Google ADK</span> <span class="tag tag-ok">Multi-Agent</span> <span class="tag tag-ok">Human-in-the-Loop</span> <span class="tag tag-ok">Firestore Memory</span></p>
</div>
<div class="grid">
<div class="card"><p class="label">Total Savings</p><p class="metric" id="savings">—</p></div>
<div class="card"><p class="label">Optimizations</p><p class="metric" id="opts">—</p></div>
<div class="card"><p class="label">Pending Approvals</p><p class="metric" id="pending">—</p></div>
</div>
<div class="card">
<button onclick="runScan()">🚀 Run Scan (Dry-Run)</button>
<button class="secondary" onclick="runScanLive()">🔥 Run Scan (Live)</button>
<button class="secondary" onclick="loadApprovals()">📋 Pending Approvals</button>
<button class="secondary" onclick="loadTraces()">📡 Agent Traces</button>
<pre id="output">Click a button to interact with AGEM...</pre>
</div>
<div class="card" id="approvals-section" style="display:none;">
<p class="label">Pending Approvals</p>
<div id="approvals-list"></div>
</div>
<script>
async function runScan(){
    document.getElementById("output").textContent="Running ADK pipeline...";
    const res=await fetch("/scan?dry_run=true",{method:"POST"});
    const data=await res.json();
    document.getElementById("output").textContent=JSON.stringify(data,null,2);
    updateStats();
}
async function runScanLive(){
    if(!confirm("Live mode will commit patches to git. Continue?")) return;
    document.getElementById("output").textContent="Running ADK pipeline (LIVE)...";
    const res=await fetch("/scan?dry_run=false",{method:"POST"});
    const data=await res.json();
    document.getElementById("output").textContent=JSON.stringify(data,null,2);
    updateStats();
}
async function loadApprovals(){
    document.getElementById("output").textContent="Loading approvals...";
    const res=await fetch("/approvals");
    const data=await res.json();
    document.getElementById("output").textContent=JSON.stringify(data,null,2);
    renderApprovals(data.pending||[]);
    document.getElementById("pending").textContent=(data.stats||{}).pending||"0";
}
async function loadTraces(){
    document.getElementById("output").textContent="Loading traces...";
    const res=await fetch("/traces");
    const data=await res.json();
    document.getElementById("output").textContent=JSON.stringify(data,null,2);
}
async function updateStats(){
    const res=await fetch("/history");
    const data=await res.json();
    document.getElementById("savings").textContent=data.total_estimated_monthly_savings||"—";
    document.getElementById("opts").textContent=data.total_optimizations||"—";
}
async function approvePatch(id){
    const res=await fetch(`/approvals/${id}/approve`,{method:"POST"});
    const data=await res.json();
    alert(data.success?"Approved!":"Failed: "+data.error);
    loadApprovals();
}
async function rejectPatch(id){
    const res=await fetch(`/approvals/${id}/reject`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason:"Rejected by user"})});
    const data=await res.json();
    alert(data.success?"Rejected!":"Failed: "+data.error);
    loadApprovals();
}
function renderApprovals(list){
    const container=document.getElementById("approvals-list");
    const section=document.getElementById("approvals-section");
    if(!list.length){section.style.display="none";container.innerHTML="<p>No pending approvals.</p>";return}
    section.style.display="block";
    container.innerHTML=list.map(a=>`
        <div class="approval-card">
            <strong>${a.resource}</strong> <span class="tag tag-warn">${a.resource_type}</span><br>
            <small>${a.patch_action}</small><br>
            <small>Savings: ${a.estimated_savings} | CWS: ${a.cws_before}</small><br>
            <button onclick="approvePatch('${a.approval_id}')">✅ Approve</button>
            <button class="danger" onclick="rejectPatch('${a.approval_id}')">❌ Reject</button>
        </div>
    `).join("");
}
updateStats();
</script></body></html>\"\"\"
    return render_template_string(html, project=PROJECT_ID)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
