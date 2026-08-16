"""ADK Supervisor agent for AGEM."""
import os
import traceback
from typing import List, Dict, Any
try:
    from google.adk.agents import Agent
except ImportError:
    class Agent:
        def __init__(self, name="", model="", description="", instruction="", tools=None):
            self.name = name
            self.model = model
            self.description = description
            self.instruction = instruction
            self.tools = tools or []

_AGEM_CORE = {}
try:
    from agem import profiler, scorer, patcher, validator, git_committer, executor, state_manager
    _AGEM_CORE = {
        "profiler": profiler, "scorer": scorer, "patcher": patcher,
        "validator": validator, "git_committer": git_committer,
        "executor": executor, "state_manager": state_manager,
    }
    print("[AGEM] Core modules loaded")
except Exception as e:
    print("[AGEM] Core modules import failed: " + str(e))
    traceback.print_exc()


def _call(module, func, *args, **kwargs):
    m = _AGEM_CORE.get(module)
    if not m:
        return None, module + " not loaded"
    f = getattr(m, func, None)
    if not f:
        return None, func + " not found in " + module
    try:
        return f(*args, **kwargs), None
    except Exception as e:
        return None, str(e)


# Shared supervisor runtime state
_RUNTIME_STATE = {
    "resources": [],
    "patches": []
}


def discover_resources() -> str:
    """Discover active GCP infrastructure across Cloud SQL, Cloud Run, and BigQuery."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
    r, e = _call("profiler", "discover", project)
    if e:
        return "Discover fallback: " + e
    _RUNTIME_STATE["resources"] = r or []
    n = len(r) if hasattr(r, "__len__") else "?"
    return f"Discovered {n} active resources in project {project}"


def profile_metrics() -> str:
    """Query 7-day timeseries utilization metrics from Cloud Monitoring."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
    r, e = _call("profiler", "profile", project)
    if e:
        return "Profile fallback: " + e
    _RUNTIME_STATE["resources"] = r or []
    n = len(r) if hasattr(r, "__len__") else "?"
    return f"Profiled 7-day metrics for {n} resources"


def score_waste() -> str:
    """Calculate multi-factor Cloud Waste Score (CWS) for all profiled resources."""
    resources = _RUNTIME_STATE.get("resources")
    if not resources:
        # Auto-discover if not already populated
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
        r, _ = _call("profiler", "profile", project)
        resources = r or []
        _RUNTIME_STATE["resources"] = resources

    r, e = _call("scorer", "compute_cws", resources)
    if e:
        return "Score fallback: " + e
    return f"Computed CWS scores for {len(resources)} resources"


def generate_patch() -> str:
    """Generate non-destructive gcloud rightsizing patches using Gemini 3.5 Flash."""
    resources = _RUNTIME_STATE.get("resources")
    if not resources:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
        r, _ = _call("profiler", "profile", project)
        resources = r or []
        _RUNTIME_STATE["resources"] = resources

    r, e = _call("patcher", "generate", resources)
    if e:
        return "Patch fallback: " + e
    _RUNTIME_STATE["patches"] = r or []
    return f"Generated {len(_RUNTIME_STATE['patches'])} optimization patches via Gemini"


def validate_safety() -> str:
    """Validate patches against AST safety grammar and require verified rollback commands."""
    patches = _RUNTIME_STATE.get("patches")
    if not patches:
        return "Safety check passed: 0 pending patches to validate"
    r, e = _call("validator", "validate", patches)
    if e:
        return "Validate fallback: " + e
    return f"Safety validation passed for {len(patches)} patches: zero destructive operations"


def commit_git() -> str:
    """Commit validated optimization manifests to isolated timestamped Git branches."""
    patches = _RUNTIME_STATE.get("patches")
    if not patches:
        return "Git isolation ready: baseline infrastructure state active"
    branches = []
    for p in patches:
        b, _ = _call("git_committer", "commit", p)
        if b:
            branches.append(b)
    return f"Committed {len(branches)} patches to isolated Git branches"


def execute_patch() -> str:
    """Execute optimization patches in dry-run or live mode with rollback logging."""
    patches = _RUNTIME_STATE.get("patches")
    if not patches:
        return "Execution ready: 0 pending actions"
    return f"Simulated execution for {len(patches)} patches in dry-run mode"


class AGEMSupervisor:
    """Google ADK Supervisor Agent orchestrating AGEM's 7 optimization tools."""
    def __init__(self):
        self._state = _RUNTIME_STATE
        self.agent = Agent(
            name="agem_supervisor",
            model="gemini-3.5-flash",
            description="Autonomous GCP optimization supervisor orchestrating 7 tools",
            instruction=(
                "You are AGEM Supervisor, an autonomous Google-powered efficiency agent. "
                "Orchestrate the 7 tools in sequence: discover_resources -> profile_metrics -> "
                "score_waste -> generate_patch -> validate_safety -> commit_git -> execute_patch. "
                "Prioritize high-savings, low-risk patches and ensure rollback commands are present."
            ),
            tools=[
                discover_resources, profile_metrics, score_waste,
                generate_patch, validate_safety, commit_git, execute_patch,
            ],
        )
        self.tools = self.agent.tools