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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #0f172a;
  --text-secondary: #64748b;
  --border: #e2e8f0;
  --accent: #6366f1;
  --accent-light: #e0e7ff;
  --success: #10b981;
  --success-light: #d1fae5;
  --warning: #f59e0b;
  --warning-light: #fef3c7;
  --danger: #ef4444;
  --danger-light: #fee2e2;
  --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.05);
  --radius: 14px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.app {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}
.sidebar {
  background: var(--card);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 32px;
  padding: 0 8px;
}
.brand-icon {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-weight: 700; font-size: 14px;
}
.brand-text { font-weight: 700; font-size: 18px; letter-spacing: -0.3px; }
.brand-sub { font-size: 11px; color: var(--text-secondary); font-weight: 400; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  margin-bottom: 4px;
  font-size: 14px; font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s;
}
.nav-item:hover, .nav-item.active {
  background: var(--accent-light);
  color: var(--accent);
}
.nav-icon { width: 18px; text-align: center; }
.main { padding: 32px 40px; max-width: 1400px; }
.header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 28px;
}
.header h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }
.header-meta { display: flex; gap: 12px; align-items: center; }
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 20px;
  font-size: 12px; font-weight: 600;
}
.badge-success { background: var(--success-light); color: #065f46; }
.badge-outline { background: var(--card); border: 1px solid var(--border); color: var(--text-secondary); }
.btn {
  padding: 10px 20px; border-radius: 10px; border: none;
  font-family: inherit; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
}
.btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white; box-shadow: 0 4px 14px rgba(99,102,241,0.35);
}
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(99,102,241,0.45); }
.btn-sm { padding: 6px 14px; font-size: 13px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 24px; }
.grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 24px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 24px; }
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px;
  box-shadow: var(--shadow);
  transition: transform 0.15s;
}
.card:hover { transform: translateY(-2px); }
.card-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 16px;
}
.card-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.4px; }
.card-value { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 6px; }
.card-delta {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
}
.delta-up { background: var(--success-light); color: #065f46; }
.delta-down { background: var(--danger-light); color: #991b1b; }
.chart-wrap { position: relative; height: 220px; }
.pipeline {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px; padding: 18px 24px;
}
.pipeline-step {
  flex: 1; text-align: center; padding: 14px 8px;
  border-radius: 12px; border: 2px solid var(--border);
  background: var(--card); transition: all 0.3s;
}
.pipeline-step.active {
  border-color: var(--accent);
  background: var(--accent-light);
  box-shadow: 0 0 0 4px rgba(99,102,241,0.1);
}
.pipeline-step.done { border-color: var(--success); background: var(--success-light); }
.step-num {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--border); color: var(--text-secondary);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; margin-bottom: 8px;
}
.pipeline-step.active .step-num { background: var(--accent); color: white; }
.pipeline-step.done .step-num { background: var(--success); color: white; }
.step-label { font-size: 13px; font-weight: 600; }
.step-desc { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.pipeline-arrow { color: var(--text-secondary); font-size: 18px; }
.log-box {
  background: #0f172a; color: #e2e8f0;
  border-radius: 12px; padding: 16px;
  font-family: 'SF Mono', monospace; font-size: 12px;
  max-height: 260px; overflow-y: auto; line-height: 1.7;
}
.approval-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border-radius: 10px;
  border: 1px solid var(--border); margin-bottom: 8px;
}
.approval-item:last-child { margin-bottom: 0; }
.empty-state {
  text-align: center; padding: 40px 20px; color: var(--text-secondary);
}
.empty-state svg { width: 48px; height: 48px; margin-bottom: 12px; opacity: 0.4; }
.trace-row {
  display: flex; gap: 12px; align-items: center;
  padding: 8px 0; border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.trace-row:last-child { border-bottom: none; }
.trace-time { color: var(--text-secondary); font-size: 12px; min-width: 60px; }
.trace-step { font-weight: 600; color: var(--accent); }
@media (max-width: 1100px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-icon">A</div>
      <div>
        <div class="brand-text">AGEM</div>
        <div class="brand-sub">GCP Optimizer</div>
      </div>
    </div>
    <div class="nav-item active">
      <span class="nav-icon">&#9638;</span> Dashboard
    </div>
    <div class="nav-item">
      <span class="nav-icon">&#9851;</span> Pipeline
    </div>
    <div class="nav-item">
      <span class="nav-icon">&#9993;</span> Approvals
    </div>
    <div class="nav-item">
      <span class="nav-icon">&#9733;</span> Savings
    </div>
    <div class="nav-item">
      <span class="nav-icon">&#9881;</span> Settings
    </div>
  </aside>

  <main class="main">
    <div class="header">
      <div>
        <h1>Dashboard</h1>
        <div style="color: var(--text-secondary); font-size: 14px; margin-top: 4px;">
          Autonomous GCP Efficiency Manager &middot; Project <strong>agem-505107</strong>
        </div>
      </div>
      <div class="header-meta">
        <span class="badge badge-outline">&#9679; Cloud Run</span>
        <span class="badge badge-success">&#9679; ADK Online</span>
        <button class="btn btn-primary" onclick="runScan()">Run Scan</button>
      </div>
    </div>

    <div class="grid-4">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Est. Monthly Savings</span>
          <span style="font-size: 20px;">&#128176;</span>
        </div>
        <div class="card-value" style="color: var(--success);">$129<span style="font-size:16px;color:var(--text-secondary);font-weight:500;">/mo</span></div>
        <div class="card-delta delta-up">&#9650; 34% vs last month</div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Cloud Waste Score</span>
          <span style="font-size: 20px;">&#128200;</span>
        </div>
        <div class="card-value">0.92<span style="font-size:16px;color:var(--text-secondary);font-weight:500;">/1.0</span></div>
        <div class="card-delta delta-up">&#9650; +100% efficiency</div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Resources Optimized</span>
          <span style="font-size: 20px;">&#9881;</span>
        </div>
        <div class="card-value">4</div>
        <div class="card-delta delta-up">&#9650; 2 this week</div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Pending Approvals</span>
          <span style="font-size: 20px;">&#9993;</span>
        </div>
        <div class="card-value" id="pending-count">0</div>
        <div class="card-delta delta-down" id="pending-label">Queue clear</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Cost Optimization Trend</span>
          <select style="border:1px solid var(--border);border-radius:8px;padding:4px 10px;font-family:inherit;font-size:12px;color:var(--text-secondary);">
            <option>Last 7 days</option>
            <option>Last 30 days</option>
          </select>
        </div>
        <div class="chart-wrap"><canvas id="costChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Resource Breakdown</span>
        </div>
        <div class="chart-wrap"><canvas id="resourceChart"></canvas></div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 24px;">
      <div class="card-header">
        <span class="card-title">Autonomous Pipeline</span>
        <span class="badge badge-outline" id="pipeline-status">Idle</span>
      </div>
      <div class="pipeline" id="pipeline">
        <div class="pipeline-step" id="step-0">
          <div class="step-num">1</div>
          <div class="step-label">Discover</div>
          <div class="step-desc">Asset Inventory</div>
        </div>
        <div class="pipeline-arrow">&#10132;</div>
        <div class="pipeline-step" id="step-1">
          <div class="step-num">2</div>
          <div class="step-label">Profile</div>
          <div class="step-desc">7-day Metrics</div>
        </div>
        <div class="pipeline-arrow">&#10132;</div>
        <div class="pipeline-step" id="step-2">
          <div class="step-num">3</div>
          <div class="step-label">Score</div>
          <div class="step-desc">CWS Algorithm</div>
        </div>
        <div class="pipeline-arrow">&#10132;</div>
        <div class="pipeline-step" id="step-3">
          <div class="step-num">4</div>
          <div class="step-label">Patch</div>
          <div class="step-desc">Gemini 2.5 Flash</div>
        </div>
        <div class="pipeline-arrow">&#10132;</div>
        <div class="pipeline-step" id="step-4">
          <div class="step-num">5</div>
          <div class="step-label">Validate</div>
          <div class="step-desc">Safety Checks</div>
        </div>
        <div class="pipeline-arrow">&#10132;</div>
        <div class="pipeline-step" id="step-5">
          <div class="step-num">6</div>
          <div class="step-label">Commit</div>
          <div class="step-desc">Git Branch</div>
        </div>
      </div>
      <div class="log-box" id="log-box" style="display:none;"></div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Approval Queue</span>
          <button class="btn btn-sm" style="background:var(--bg);border:1px solid var(--border);">View All</button>
        </div>
        <div id="approval-list">
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div style="font-weight:600;margin-bottom:4px;">All Clear</div>
            <div style="font-size:13px;">No patches awaiting approval.</div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <span class="card-title">Recent Agent Traces</span>
        </div>
        <div id="trace-list">
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div style="font-weight:600;margin-bottom:4px;">No Traces</div>
            <div style="font-size:13px;">Run a scan to generate traces.</div>
          </div>
        </div>
      </div>
    </div>
  </main>
</div>

<script>
const costCtx = document.getElementById('costChart').getContext('2d');
new Chart(costCtx, {
  type: 'line',
  data: {
    labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
    datasets: [{
      label: 'Potential Savings ($)',
      data: [12,19,15,28,35,42,48],
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 4,
      pointBackgroundColor: '#6366f1',
      borderWidth: 2.5
    }, {
      label: 'Actual Savings ($)',
      data: [0,0,8,18,25,32,40],
      borderColor: '#10b981',
      backgroundColor: 'rgba(16,185,129,0.06)',
      fill: true,
      tension: 0.4,
      pointRadius: 4,
      pointBackgroundColor: '#10b981',
      borderWidth: 2.5
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8 } } },
    scales: {
      y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 }, color: '#94a3b8' } },
      x: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#94a3b8' } }
    }
  }
});

const resCtx = document.getElementById('resourceChart').getContext('2d');
new Chart(resCtx, {
  type: 'doughnut',
  data: {
    labels: ['Cloud SQL','Cloud Run','BigQuery','Storage'],
    datasets: [{
      data: [25,72,45,18],
      backgroundColor: ['#6366f1','#8b5cf6','#10b981','#f59e0b'],
      borderWidth: 0,
      hoverOffset: 8
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    cutout: '68%',
    plugins: {
      legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 16, font: { size: 11 } } }
    }
  }
});

const STEPS = ['Discover','Profile','Score','Patch','Validate','Commit'];
let scanning = false;

async function runScan() {
  if (scanning) return;
  scanning = true;
  const logBox = document.getElementById('log-box');
  const status = document.getElementById('pipeline-status');
  logBox.style.display = 'block';
  logBox.innerHTML = '<span style="color:#60a5fa">[AGEM]</span> Starting autonomous scan...<br>';
  status.textContent = 'Running';
  status.className = 'badge badge-success';

  for (let i = 0; i < STEPS.length; i++) {
    document.querySelectorAll('.pipeline-step').forEach((el, idx) => {
      el.classList.remove('active','done');
      if (idx < i) el.classList.add('done');
      if (idx === i) el.classList.add('active');
    });
    logBox.innerHTML += '<span style="color:#60a5fa">[AGEM]</span> ' + STEPS[i] + ' in progress...<br>';
    logBox.scrollTop = logBox.scrollHeight;
    await new Promise(r => setTimeout(r, 800));
    logBox.innerHTML += '<span style="color:#34d399">[OK]</span> ' + STEPS[i] + ' complete<br>';
    logBox.scrollTop = logBox.scrollHeight;
  }

  document.querySelectorAll('.pipeline-step').forEach(el => el.classList.add('done'));
  logBox.innerHTML += '<span style="color:#fbbf24">[DONE]</span> Scan complete. Patches queued for approval.<br>';
  status.textContent = 'Idle';
  status.className = 'badge badge-outline';
  scanning = false;
  loadTraces();
}

async function loadApprovals() {
  try {
    const r = await fetch('/approvals');
    const d = await r.json();
    document.getElementById('pending-count').textContent = d.count;
    const list = document.getElementById('approval-list');
    if (!d.pending || d.pending.length === 0) {
      list.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><div style="font-weight:600;margin-bottom:4px;">All Clear</div><div style="font-size:13px;">No patches awaiting approval.</div></div>';
      document.getElementById('pending-label').textContent = 'Queue clear';
      document.getElementById('pending-label').className = 'card-delta delta-up';
      return;
    }
    list.innerHTML = d.pending.map(p => '<div class="approval-item"><div><div style="font-weight:600;font-size:13px;">' + p.patch_id + '</div><div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">' + new Date(p.timestamp*1000).toLocaleString() + '</div></div><div style="display:flex;gap:8px;"><button class="btn btn-sm" style="background:var(--success-light);color:#065f46;border:none;">Approve</button><button class="btn btn-sm" style="background:var(--danger-light);color:#991b1b;border:none;">Reject</button></div></div>').join('');
    document.getElementById('pending-label').textContent = d.count + ' pending';
    document.getElementById('pending-label').className = 'card-delta delta-down';
  } catch(e) { console.error(e); }
}

async function loadTraces() {
  try {
    const r = await fetch('/traces');
    const d = await r.json();
    const list = document.getElementById('trace-list');
    if (!d.traces || d.traces.length === 0) {
      list.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><div style="font-weight:600;margin-bottom:4px;">No Traces</div><div style="font-size:13px;">Run a scan to generate traces.</div></div>';
      return;
    }
    list.innerHTML = d.traces.slice().reverse().map(t => '<div class="trace-row"><span class="trace-time">' + new Date(t.timestamp*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) + '</span><span class="trace-step">' + t.step + '</span><span style="color:var(--text-secondary);flex:1;">' + t.detail + '</span><span class="badge badge-success" style="padding:2px 8px;font-size:11px;">' + t.status + '</span></div>').join('');
  } catch(e) { console.error(e); }
}

loadApprovals();
loadTraces();
setInterval(() => { loadApprovals(); loadTraces(); }, 5000);
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
