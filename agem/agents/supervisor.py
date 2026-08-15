"""ADK Supervisor agent for AGEM."""
import os
import traceback
from google.adk.agents import Agent

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


def discover_resources() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
    r, e = _call("profiler", "discover", project)
    if e:
        return "Discover fallback: " + e
    n = len(r) if hasattr(r, "__len__") else "?"
    return "Discovered " + str(n) + " resources"


def profile_metrics() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")
    r, e = _call("profiler", "profile", project)
    if e:
        return "Profile fallback: " + e
    n = len(r) if hasattr(r, "__len__") else "?"
    return "Profiled " + str(n) + " resources"


def score_waste() -> str:
    r, e = _call("scorer", "compute_cws")
    if e:
        return "Score fallback: " + e
    return "CWS = " + str(r)


def generate_patch() -> str:
    r, e = _call("patcher", "generate")
    if e:
        return "Patch fallback: " + e
    return "Patch: " + str(r)


def validate_safety() -> str:
    r, e = _call("validator", "validate")
    if e:
        return "Validate fallback: " + e
    return "Validation: " + str(r)


def commit_git() -> str:
    r, e = _call("git_committer", "commit")
    if e:
        return "Git fallback: " + e
    return "Git: " + str(r)


def execute_patch() -> str:
    r, e = _call("executor", "execute")
    if e:
        return "Execute fallback: " + e
    return "Execute: " + str(r)


class AGEMSupervisor:
    def __init__(self):
        self.agent = Agent(
            name="agem_supervisor",
            model="gemini-2.5-flash",
            description="Autonomous GCP optimization supervisor",
            instruction=(
                "You are AGEM Supervisor. Orchestrate: discover -> profile -> score -> patch -> validate -> commit -> execute. "
                "Require rollback commands and quantify savings in dollars per month."
            ),
            tools=[
                discover_resources, profile_metrics, score_waste,
                generate_patch, validate_safety, commit_git, execute_patch,
            ],
        )
        self.tools = self.agent.tools