# AGEM — Autonomous Google-powered Efficiency Manager

**Track:** Taskmaster — All Things Agentic Hackathon 2026

AGEM is an autonomous, closed-loop cloud optimization agent for Google Cloud Platform. It discovers resources, profiles performance metrics, scores waste via a proprietary Cloud Waste Score (CWS), generates optimization patches via Gemini 3.6 Flash, validates them for safety, commits approved patches to isolated git branches, and remembers every action in Firestore — zero human intervention.

---

## What AGEM Does (The Closed Loop)
Discover → Profile → Score → Patch → Validate → Commit → Execute → Remember
✅        ✅       ✅       ✅        ✅         ✅        ✅         ✅
plain

1. **Discovers** all Cloud SQL, Cloud Run, and BigQuery resources via **Cloud Asset Inventory API**
2. **Profiles** 7-day CPU, memory, and utilization metrics via **Cloud Monitoring API**
3. **Scores** each resource with the **Cloud Waste Score (CWS)** — a weighted model (0.35 cost, 0.30 performance, 0.20 security, 0.15 reliability) tuned for GCP economics
4. **Generates** optimization patches via **Gemini 3.6 Flash** with specific gcloud commands
5. **Validates** every patch for destructive operations, rollback presence, and savings estimates
6. **Commits** approved patches to isolated git branches (`agem/auto-optimize-*`)
7. **Executes** patches in dry-run mode (set `dry_run=False` to apply live)
8. **Remembers** every optimization in **Firestore** — skips resources optimized in the last 24h

---

## Architecture
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Cloud Asset    │     │  Cloud          │     │  Cloud          │
│  Inventory API  │     │  Monitoring API │     │  Billing API    │
└────────┬────────┘     └────────┬────────┘     └─────────────────┘
│                         │
└───────────┬─────────────┘
▼
┌─────────────┐
│   AGEM        │
│   Profiler    │
└──────┬──────┘
▼
┌─────────────┐
│   CWS         │
│   Scorer      │
└──────┬──────┘
▼
┌─────────────┐
│  Gemini 3.6   │
│   Flash       │
│  (Patch Gen)  │
└──────┬──────┘
▼
┌─────────────┐
│  Validator    │
│  (Safety)     │
└──────┬──────┘
▼
┌─────────────────────────┐
│                         │
▼                         ▼
┌──────────┐            ┌──────────────┐
│   Git    │            │  Firestore   │
│ Committer│            │  (Memory)    │
└──────────┘            └──────────────┘
│
▼
┌──────────┐
│ Executor │
│(Dry-run) │
└──────────┘
plain

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/rakeshraks2612-maker/AGEM.git
cd AGEM

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure GCP
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 5. Add your Gemini API key
# Edit config/config.yaml and replace YOUR_AI_STUDIO_API_KEY_HERE

# 6. Run AGEM
make run
# or: python -m agem.profiler
Demo Results
AGEM scanned project agem-505107 and found:
Table
Resource	Waste Found	CWS Score	Patch	Savings
agem-demo-db (Cloud SQL)	4.28% CPU on db-n1-standard-2	0.46/1.0 CRITICAL	Downsize to db-n1-standard-1	~$25/month
agem-demo-service (Cloud Run)	4Gi RAM, 2 CPU, 2 min instances	0.80 waste	Reduce to 512Mi, 1 CPU, 0 min	~$72/month
Total estimated savings: $129.12/month — found and patched autonomously.
On the second run (within 24h), AGEM skipped the Cloud SQL instance because Firestore remembered it was already optimized. This is cross-session memory.
Technologies Used
Table
Technology	Purpose
Gemini 3.6 Flash (AI Studio)	Patch generation & reasoning
Google ADK	Agent orchestration framework
Cloud Asset Inventory API	Resource discovery
Cloud Monitoring API	Performance metrics
Cloud Billing API	Cost data for scoring
Firestore	Persistent optimization history & cross-session memory
Cloud Run	Agent deployment target
Git	Patch isolation & versioning
Project Structure
plain
AGEM/
├── agem/
│   ├── __init__.py
│   ├── profiler.py       # Resource discovery & metrics
│   ├── scorer.py         # Cloud Waste Score (CWS)
│   ├── patcher.py        # Gemini patch generation
│   ├── validator.py      # Safety validation
│   ├── git_committer.py  # Git branch & commit
│   ├── executor.py       # Dry-run / live execution
│   └── state_manager.py  # Firestore persistence
├── config/
│   └── config.yaml       # GCP project, API keys, thresholds
├── prompts/
│   └── optimize.txt      # Gemini system prompt
├── requirements.txt
├── Dockerfile
├── Makefile
└── README.md
Safety & Guardrails
No destructive operations — patches are scanned for delete, DROP, rm -rf, IAM changes
Rollback required — every patch must include an exact rollback command
Dollar savings required — patches without quantified savings are rejected
Dry-run by default — execution is simulated unless dry_run=False is set
24h memory — Firestore prevents re-optimization of the same resource within 24 hours
License
MIT
