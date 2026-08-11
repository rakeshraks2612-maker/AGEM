import os
import time
import json
from flask import Flask, jsonify

from agem.profiler import discover_resources, profile_resource
from agem.scorer import calculate_cws
from agem.patcher import generate_patch
from agem.validator import validate_patch
from agem.git_committer import commit_patch
from agem.state_manager import StateManager

app = Flask(__name__)
state_manager = StateManager()

# Detect Cloud Run environment
RUNNING_IN_CLOUD = os.environ.get("K_SERVICE") is not None

@app.route("/")
def index():
    return jsonify({
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"),
        "status": "AGEM is live",
        "mode": "cloud" if RUNNING_IN_CLOUD else "local"
    })

@app.route("/scan", methods=["POST"])
def scan():
    start = time.time()
    
    try:
        resources = discover_resources()
    except Exception as e:
        return jsonify({"error": "Discovery failed", "detail": str(e)}), 500

    results = []
    approved = 0
    skipped = 0

    for resource in resources:
        name = resource.get("name", "unknown").split("/")[-1]
        res_type = resource.get("asset_type", "unknown").split("/")[-1]

        # Check Firestore history
        if state_manager.was_recently_optimized(name):
            skipped += 1
            results.append({
                "resource": name,
                "type": res_type,
                "status": "skipped",
                "reason": "Optimized in last 24h"
            })
            continue

        try:
            # Profile & Score
            metrics = profile_resource(resource)
            score = calculate_cws(resource, metrics)
            score_val = getattr(score, 'total', score) if hasattr(score, 'total') else score

            # Generate Patch
            patch = generate_patch(resource, metrics, score)
            patch_action = getattr(patch, 'action', str(patch))
            patch_savings = getattr(patch, 'estimated_savings', 'N/A')

            # Validate
            validation = validate_patch(patch)
            item = {
                "resource": name,
                "type": res_type,
                "cws_before": score_val,
                "patch_action": patch_action,
                "estimated_savings": patch_savings,
                "validation": validation,
            }

            if isinstance(validation, dict) and validation.get("passed"):
                if RUNNING_IN_CLOUD:
                    # Cloud Run: simulate git, don't actually push
                    item["status"] = "approved"
                    item["branch"] = f"agem/auto-optimize-{name}-{int(time.time())}"
                    item["git_note"] = "Git commit simulated in Cloud Run (no GH credentials)"
                    item["savings"] = patch_savings
                    approved += 1
                else:
                    # Local: real git commit
                    commit = commit_patch(patch)
                    if commit and getattr(commit, 'success', False):
                        state_manager.record_optimization(
                            resource_name=name,
                            resource_type=res_type,
                            cws_before=score_val,
                            patch_action=patch_action,
                            estimated_savings=patch_savings,
                            branch_name=getattr(commit, 'branch', 'unknown'),
                            status="committed",
                        )
                        item["status"] = "approved"
                        item["branch"] = getattr(commit, 'branch', 'unknown')
                        item["savings"] = patch_savings
                        approved += 1
                    else:
                        item["status"] = "commit_failed"
            else:
                item["status"] = "rejected"
        except Exception as e:
            item = {
                "resource": name,
                "type": res_type,
                "status": "error",
                "error": str(e)
            }

        results.append(item)

    try:
        savings = state_manager.get_total_estimated_savings()
        if isinstance(savings, dict):
            total_savings = savings.get("total_estimated_monthly_savings", 0)
            total_opts = savings.get("total_optimizations", 0)
        else:
            total_savings = 0
            total_opts = 0
    except Exception:
        total_savings = 0
        total_opts = 0

    return jsonify({
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "agem-505107"),
        "resources_scanned": len(resources),
        "patches_approved": approved,
        "resources_skipped": skipped,
        "total_estimated_monthly_savings": total_savings,
        "total_optimizations_in_history": total_opts,
        "scan_duration_sec": round(time.time() - start, 2),
        "mode": "cloud" if RUNNING_IN_CLOUD else "local",
        "results": results,
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
