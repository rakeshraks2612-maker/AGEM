"""Base wrappers that bridge existing AGEM classes to ADK Tools."""
import os
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Lazy imports to avoid breaking if ADK isn't installed
try:
    from google.adk.tools import tool
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    def tool(func): return func

from agem.profiler import Profiler
from agem.scorer import Scorer
from agem.patcher import Patcher
from agem.validator import Validator
from agem.git_committer import GitCommitter
from agem.state_manager import StateManager

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

# ── Singleton instances (reused across agent calls) ──────────
_profiler = None
_scorer = None
_patcher = None
_validator = None
_gitter = None
_state = None

def _get_profiler():
    global _profiler
    if _profiler is None:
        _profiler = Profiler()
    return _profiler

def _get_scorer():
    global _scorer
    if _scorer is None:
        _scorer = Scorer()
    return _scorer

def _get_patcher():
    global _patcher
    if _patcher is None:
        _patcher = Patcher()
    return _patcher

def _get_validator():
    global _validator
    if _validator is None:
        _validator = Validator()
    return _validator

def _get_gitter():
    global _gitter
    if _gitter is None:
        _gitter = GitCommitter()
    return _gitter

def _get_state():
    global _state
    if _state is None:
        _state = StateManager()
    return _state

# ── ADK Tools ────────────────────────────────────────────────
@tool
def discover_gcp_resources() -> str:
    """Discover all GCP resources in the project using Cloud Asset Inventory.
    
    Returns:
        JSON string with discovered resources (Cloud SQL, Cloud Run, etc.)
    """
    prof = _get_profiler()
    try:
        resources = prof.discover_resources()
        if not resources:
            return json.dumps({"resources": [], "note": "No resources found or permission denied"})
        # Serialize to JSON-safe format
        serialized = []
        for r in resources:
            if isinstance(r, dict):
                serialized.append(r)
            else:
                serialized.append({
                    "name": getattr(r, "name", str(r)),
                    "type": getattr(r, "asset_type", "unknown"),
                    "display_name": getattr(r, "display_name", getattr(r, "name", "unknown"))
                })
        return json.dumps({"resources": serialized, "count": len(serialized)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "resources": []})

@tool
def profile_resource(resource_json: str) -> str:
    """Profile a single GCP resource and collect 7-day utilization metrics.
    
    Args:
        resource_json: JSON string representing the resource to profile.
    
    Returns:
        JSON string with metrics (cpu, memory, disk, etc.)
    """
    prof = _get_profiler()
    try:
        resource = json.loads(resource_json)
        metrics = prof.profile_resource(resource)
        if isinstance(metrics, dict):
            return json.dumps({"metrics": metrics, "resource": resource.get("name", "unknown")})
        return json.dumps({"metrics": getattr(metrics, "__dict__", str(metrics)), "resource": resource.get("name", "unknown")})
    except Exception as e:
        return json.dumps({"error": str(e), "metrics": {}})

@tool
def calculate_waste_score(resource_json: str, metrics_json: str) -> str:
    """Calculate the Cloud Waste Score (CWS) for a resource.
    
    Args:
        resource_json: JSON string with resource metadata.
        metrics_json: JSON string with utilization metrics.
    
    Returns:
        JSON string with CWS breakdown (cost, performance, security, reliability).
    """
    scorer = _get_scorer()
    try:
        resource = json.loads(resource_json)
        metrics = json.loads(metrics_json)
        score = scorer.score_cloud_sql(metrics) if "sql" in str(resource) else scorer.calculate_cws(resource, metrics)
        result = {
            "total": getattr(score, "total", float(score) if isinstance(score, (int, float)) else 0.5),
            "cost": getattr(score, "cost", 0),
            "performance": getattr(score, "performance", 0),
            "security": getattr(score, "security", 0),
            "reliability": getattr(score, "reliability", 0),
            "resource": resource.get("name", "unknown")
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "total": 0.5, "cost": 0, "performance": 0, "security": 0, "reliability": 0})

@tool
def generate_optimization_patch(resource_json: str, score_json: str) -> str:
    """Generate an optimization patch using Gemini.
    
    Args:
        resource_json: JSON string with resource metadata.
        score_json: JSON string with CWS score.
    
    Returns:
        JSON string with patch details (action, savings, rollback command).
    """
    patcher = _get_patcher()
    try:
        resource = json.loads(resource_json)
        score = json.loads(score_json)
        patch = patcher.generate_patch(resource, score)
        result = {
            "action": getattr(patch, "action", patch.get("action", "N/A")) if hasattr(patch, "action") or isinstance(patch, dict) else str(patch),
            "estimated_savings": getattr(patch, "estimated_savings", patch.get("estimated_savings", "N/A")) if hasattr(patch, "estimated_savings") or isinstance(patch, dict) else "N/A",
            "rollback": getattr(patch, "rollback", patch.get("rollback", "N/A")) if hasattr(patch, "rollback") or isinstance(patch, dict) else "N/A",
            "patch_type": getattr(patch, "patch_type", patch.get("patch_type", "gcloud")) if hasattr(patch, "patch_type") or isinstance(patch, dict) else "gcloud",
            "before": getattr(patch, "before", patch.get("before", "")) if hasattr(patch, "before") or isinstance(patch, dict) else "",
            "after": getattr(patch, "after", patch.get("after", "")) if hasattr(patch, "after") or isinstance(patch, dict) else "",
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "action": "N/A", "estimated_savings": "N/A", "rollback": "N/A"})

@tool
def validate_patch_safety(patch_json: str, resource_json: str) -> str:
    """Validate that a patch is safe (no destructive ops, has rollback, has savings).
    
    Args:
        patch_json: JSON string with patch details.
        resource_json: JSON string with resource metadata.
    
    Returns:
        JSON string with validation result (passed, checks, warnings, errors).
    """
    validator = _get_validator()
    try:
        patch_dict = json.loads(patch_json)
        resource = json.loads(resource_json)
        # Convert dict to namespace for validator
        from types import SimpleNamespace
        patch_ns = SimpleNamespace(**patch_dict)
        result = validator.validate(patch_ns, resource)
        return json.dumps({
            "passed": getattr(result, "passed", result.get("passed", False)) if hasattr(result, "passed") or isinstance(result, dict) else False,
            "checks": getattr(result, "checks", result.get("checks", {})) if hasattr(result, "checks") or isinstance(result, dict) else {},
            "warnings": getattr(result, "warnings", result.get("warnings", [])) if hasattr(result, "warnings") or isinstance(result, dict) else [],
            "errors": getattr(result, "errors", result.get("errors", [])) if hasattr(result, "errors") or isinstance(result, dict) else [],
        }, indent=2)
    except Exception as e:
        return json.dumps({"passed": False, "error": str(e), "checks": {}, "warnings": [], "errors": [str(e)]})

@tool
def commit_patch_to_git(patch_json: str) -> str:
    """Commit an approved patch to an isolated git branch.
    
    Args:
        patch_json: JSON string with patch details.
    
    Returns:
        JSON string with commit result (success, branch, hash).
    """
    gitter = _get_gitter()
    try:
        patch_dict = json.loads(patch_json)
        from types import SimpleNamespace
        patch_ns = SimpleNamespace(**patch_dict)
        result = gitter.commit_patch(patch_ns)
        return json.dumps({
            "success": getattr(result, "success", True),
            "branch": getattr(result, "branch", "unknown"),
            "hash": getattr(result, "hash", getattr(result, "commit_hash", "unknown")),
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "branch": None, "hash": None})

@tool
def record_optimization_history(resource_name: str, resource_type: str, cws_before: float, patch_action: str, estimated_savings: str, branch_name: str) -> str:
    """Record an optimization in Firestore for cross-session memory.
    
    Args:
        resource_name: Name of the optimized resource.
        resource_type: Type of resource (cloud_sql, cloud_run, etc.).
        cws_before: CWS score before optimization.
        patch_action: Description of the patch.
        estimated_savings: Estimated monthly savings.
        branch_name: Git branch where patch is committed.
    
    Returns:
        JSON string confirming the record was saved.
    """
    state = _get_state()
    try:
        state.record_optimization(
            resource_name=resource_name,
            resource_type=resource_type,
            cws_before=cws_before,
            patch_action=patch_action,
            estimated_savings=estimated_savings,
            branch_name=branch_name,
            status="committed"
        )
        return json.dumps({"success": True, "message": f"Recorded optimization for {resource_name}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def check_recent_optimization(resource_name: str) -> str:
    """Check if a resource was optimized in the last 24 hours.
    
    Args:
        resource_name: Name of the resource to check.
    
    Returns:
        JSON string with was_optimized (bool) and hours_since.
    """
    state = _get_state()
    try:
        was_opt = state.was_recently_optimized(resource_name, hours=24)
        return json.dumps({"was_optimized": was_opt, "resource": resource_name, "window_hours": 24})
    except Exception as e:
        return json.dumps({"was_optimized": False, "error": str(e), "resource": resource_name})

# ── Tool Registry ────────────────────────────────────────────
AGEM_TOOLS = [
    discover_gcp_resources,
    profile_resource,
    calculate_waste_score,
    generate_optimization_patch,
    validate_patch_safety,
    commit_patch_to_git,
    record_optimization_history,
    check_recent_optimization,
]
