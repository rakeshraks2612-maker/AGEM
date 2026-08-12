"""AGEM Supervisor Agent — orchestrates the entire optimization pipeline."""
import os
import json
import time
from typing import Dict, List, Any

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    Agent = None
    Runner = None
    InMemorySessionService = None

from .base import AGEM_TOOLS, _get_state
from .approval_queue import ApprovalQueue
from .tracer import AgentTracer

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107")

SUPERVISOR_INSTRUCTION = \"\"\"You are AGEM Supervisor, an autonomous cloud optimization engineer for Google Cloud Platform.

Your mission: discover over-provisioned resources, score waste, generate safe patches, and execute optimizations.

PIPELINE RULES:
1. DISCOVER: Call discover_gcp_resources to find all resources.
2. FILTER: For each resource, call check_recent_optimization. Skip if optimized in last 24h.
3. PROFILE: Call profile_resource for each unoptimized resource.
4. SCORE: Call calculate_waste_score with resource + metrics.
5. PATCH: If CWS total > 0.5 (wasteful), call generate_optimization_patch.
6. VALIDATE: Call validate_patch_safety on every patch.
7. APPROVE: If validation passes AND estimated savings > $50/month, queue for human approval.
   If savings <= $50/month, auto-approve and execute.
8. EXECUTE: Call commit_patch_to_git, then record_optimization_history.
9. REPORT: Return a final summary of all actions taken.

SAFETY:
- NEVER approve patches with destructive ops
- ALWAYS require rollback commands
- ALWAYS quantify savings in dollars
- When in doubt, reject the patch

Respond in structured JSON only.\"\"\"

class AGEMSupervisor:
    """Wraps the ADK Supervisor agent and executes the AGEM pipeline."""
    
    def __init__(self):
        self.tracer = AgentTracer()
        self.approval_queue = ApprovalQueue()
        self.session_service = InMemorySessionService() if ADK_AVAILABLE and InMemorySessionService else None
        self.runner = None
        if ADK_AVAILABLE and Agent and Runner:
            self.agent = Agent(
                model=\"gemini-3.6-flash\",
                name=\"agem_supervisor\",
                description=\"Autonomous GCP optimization supervisor\",
                instruction=SUPERVISOR_INSTRUCTION,
                tools=AGEM_TOOLS,
            )
            self.runner = Runner(agent=self.agent, session_service=self.session_service)
    
    def run_pipeline(self, force: bool = False, dry_run: bool = True) -> Dict[str, Any]:
        \"\"\"Execute the full AGEM pipeline.
        
        Args:
            force: Bypass 24h memory check.
            dry_run: If True, don't actually commit patches (simulate).
        
        Returns:
            Dict with scan results, approvals, and traces.
        \"\"\"        
        start = time.time()
        trace_id = f\"trace-{int(start)}"
        self.tracer.start_trace(trace_id, {\"force\": force, "dry_run": dry_run})
        
        results = []
        approved = 0
        skipped = 0
        pending = 0
        errors = []
        
        # Step 1: Discover
        self.tracer.log_step(trace_id, "discovery", "Starting resource discovery")
        try:
            from .base import discover_gcp_resources
            disc_raw = discover_gcp_resources()
            disc = json.loads(disc_raw)
            resources = disc.get("resources", [])
            self.tracer.log_step(trace_id, "discovery", f"Found {len(resources)} resources", {"count": len(resources)})
        except Exception as e:
            errors.append(f"Discovery failed: {e}")
            resources = []
            self.tracer.log_step(trace_id, "discovery", f"Failed: {e}", {"error": str(e)})
        
        # Step 2-8: Process each resource
        for resource in resources:
            name = resource.get("display_name") or resource.get("name", "unknown").split("/")[-1]
            res_type = resource.get("type") or resource.get("asset_type", "unknown").split("/")[-1]
            
            # Check memory
            if not force:
                try:
                    from .base import check_recent_optimization
                    recent = json.loads(check_recent_optimization(name))
                    if recent.get("was_optimized"):
                        skipped += 1
                        self.tracer.log_step(trace_id, "memory", f"Skipped {name} (recently optimized)", {"resource": name})
                        results.append({"resource": name, "type": res_type, "status": "skipped", "reason": "24h memory"})
                        continue
                except Exception as e:
                    self.tracer.log_step(trace_id, "memory", f"Memory check error for {name}: {e}", {"resource": name})
            
            item = {"resource": name, "type": res_type}
            try:
                # Profile
                self.tracer.log_step(trace_id, "profile", f"Profiling {name}", {"resource": name})
                from .base import profile_resource
                prof_raw = profile_resource(json.dumps(resource))
                prof = json.loads(prof_raw)
                metrics = prof.get("metrics", {})
                
                # Score
                self.tracer.log_step(trace_id, "score", f"Scoring {name}", {"resource": name})
                from .base import calculate_waste_score
                score_raw = calculate_waste_score(json.dumps(resource), json.dumps(metrics))
                score = json.loads(score_raw)
                score_total = score.get("total", 0.5)
                item["cws_before"] = score_total
                
                # Skip if not wasteful
                if score_total < 0.5:
                    item["status"] = "not_wasteful"
                    results.append(item)
                    self.tracer.log_step(trace_id, "score", f"{name} not wasteful ({score_total})", {"resource": name, "cws": score_total})
                    continue
                
                # Patch
                self.tracer.log_step(trace_id, "patch", f"Generating patch for {name}", {"resource": name})
                from .base import generate_optimization_patch
                patch_raw = generate_optimization_patch(json.dumps(resource), json.dumps(score))
                patch = json.loads(patch_raw)
                item["patch_action"] = patch.get("action", "N/A")
                item["estimated_savings"] = patch.get("estimated_savings", "N/A")
                
                # Validate
                self.tracer.log_step(trace_id, "validate", f"Validating patch for {name}", {"resource": name})
                from .base import validate_patch_safety
                val_raw = validate_patch_safety(json.dumps(patch), json.dumps(resource))
                validation = json.loads(val_raw)
                item["validation"] = validation
                
                if not validation.get("passed", False):
                    item["status"] = "rejected"
                    results.append(item)
                    self.tracer.log_step(trace_id, "validate", f"{name} patch rejected", {"resource": name, "validation": validation})
                    continue
                
                # Approval decision
                savings_str = patch.get("estimated_savings", "$0")
                try:
                    savings_num = float(''.join(c for c in savings_str if c.isdigit() or c == '.'))
                except ValueError:
                    savings_num = 0
                
                if savings_num > 50 and not force:
                    # Queue for human approval
                    approval_id = self.approval_queue.create({
                        "resource": name,
                        "type": res_type,
                        "cws_before": score_total,
                        "patch": patch,
                        "validation": validation,
                        "trace_id": trace_id,
                    })
                    item["status"] = "pending_approval"
                    item["approval_id"] = approval_id
                    pending += 1
                    self.tracer.log_step(trace_id, "approval", f"{name} queued for approval (savings: {savings_str})", {"resource": name, "approval_id": approval_id})
                else:
                    # Auto-approve
                    if not dry_run:
                        from .base import commit_patch_to_git
                        commit_raw = commit_patch_to_git(json.dumps(patch))
                        commit = json.loads(commit_raw)
                        item["branch"] = commit.get("branch", "unknown")
                    else:
                        item["branch"] = f"agem/auto-optimize-{name}-{int(time.time())}"
                        item["git_note"] = "Simulated (dry-run)"
                    
                    from .base import record_optimization_history
                    record_optimization_history(name, res_type, score_total, patch.get("action", ""), patch.get("estimated_savings", ""), item["branch"])
                    item["status"] = "approved"
                    approved += 1
                    self.tracer.log_step(trace_id, "execute", f"{name} approved and executed", {"resource": name, "branch": item["branch"]})
                
            except Exception as e:
                item["status"] = "error"
                item["error"] = str(e)
                errors.append(f"{name}: {e}")
                self.tracer.log_step(trace_id, "error", f"Error processing {name}: {e}", {"resource": name, "error": str(e)})
            
            results.append(item)
        
        # Finalize trace
        self.tracer.end_trace(trace_id, {
            "resources_scanned": len(resources),
            "approved": approved,
            "skipped": skipped,
            "pending": pending,
            "errors": errors,
            "duration_sec": round(time.time() - start, 2),
        })
        
        return {
            "project": PROJECT_ID,
            "trace_id": trace_id,
            "resources_scanned": len(resources),
            "patches_approved": approved,
            "resources_skipped": skipped,
            "pending_approval": pending,
            "scan_duration_sec": round(time.time() - start, 2),
            "results": results,
            "errors": errors,
        }
