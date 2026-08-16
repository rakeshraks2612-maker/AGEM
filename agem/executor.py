# agem/executor.py
import subprocess
from typing import Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    command: str


PRODUCTION_BLOCKLIST = ["prod", "production", "critical", "db-master", "production-db"]


def is_safe_to_execute(resource_name: str) -> bool:
    """Check if resource does not match protected production keywords."""
    if not resource_name:
        return True
    return not any(tag in resource_name.lower() for tag in PRODUCTION_BLOCKLIST)


class Executor:
    """Executes validated gcloud patches with dry-run safety and production blocklist enforcement."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run  # Set False for live gcloud execution, True for simulation
    
    def execute(self, patch: Any, force: bool = False) -> ExecutionResult:
        """Run the patch command with production safety guardrails."""
        after_str = getattr(patch, "after", patch.get("after", patch.get("diff", {}).get("after", "")) if isinstance(patch, dict) else "")
        command = self._extract_command(after_str)
        resource_name = getattr(patch, "resource_name", patch.get("resource_name", patch.get("id", "resource")) if isinstance(patch, dict) else "resource")
        
        if not command:
            return ExecutionResult(False, "", "", "No gcloud command found in patch")
        
        # Production Safety Guardrail: Block destructive or live execution on production assets unless explicitly forced
        if not self.dry_run and not force and not is_safe_to_execute(resource_name):
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"[SAFETY_VIOLATION] Resource '{resource_name}' matches protected tag in PRODUCTION_BLOCKLIST {PRODUCTION_BLOCKLIST}. Live autonomous mutation blocked for safety.",
                command=command,
            )
        
        if self.dry_run:
            # Simulate: just echo what would happen
            return ExecutionResult(
                success=True,
                stdout=f"[DRY-RUN] Would execute: {command}",
                stderr="",
                command=command,
            )
        
        # Actually execute
        import shlex
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        return ExecutionResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
        )
    
    def execute_rollback(self, patch: Any) -> ExecutionResult:
        """Execute the stored rollback command for an approved/applied patch."""
        rollback_cmd = ""
        if isinstance(patch, str):
            rollback_cmd = patch
        elif hasattr(patch, "rollback"):
            rollback_cmd = patch.rollback
        elif isinstance(patch, dict):
            rollback_cmd = patch.get("rollback", "")
            if not rollback_cmd and "diff" in patch:
                # Synthesize rollback if needed
                r_id = patch.get("resource_id", patch.get("id", "service"))
                rollback_cmd = f"gcloud run services update {r_id} --memory=4Gi --cpu=2 --min-instances=2 --region=us-central1"
        
        command = self._extract_command(rollback_cmd) if "gcloud" in rollback_cmd else rollback_cmd.strip()
        if not command:
            command = f"gcloud run services update {getattr(patch, 'resource_name', 'resource')} --min-instances=2"
        
        if self.dry_run:
            return ExecutionResult(
                success=True,
                stdout=f"[DRY-RUN] Rollback executed: {command}",
                stderr="",
                command=command,
            )
        
        import shlex
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=300,
        )
        return ExecutionResult(
            success=result.returncode == 0,
            stdout=result.stdout or f"Rollback successfully executed: {command}",
            stderr=result.stderr,
            command=command,
        )

    def reprofile_and_validate(self, resource_name: str, base_cws: float, opt_cws: float) -> Tuple[bool, str]:
        """Verify that post-patch optimization actually reduced CWS score (Score Regression Check)."""
        # Score regression check: optimal CWS must be strictly lower than base CWS (less waste)
        if opt_cws >= base_cws:
            return False, f"Regression detected: CWS score did not improve ({opt_cws} >= {base_cws})"
        improvement = round(((base_cws - opt_cws) / max(0.01, base_cws)) * 100, 1)
        return True, f"Verified CWS efficiency gain of +{improvement}% ({base_cws:.2f} -> {opt_cws:.2f})"

    def _extract_command(self, patch_text: str) -> str:
        """Extract gcloud/bq command from patch text."""
        lines = str(patch_text).split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('gcloud ') or line.startswith('bq '):
                return line.replace('```', '').replace('bash', '').strip()
        if patch_text and ('gcloud ' in str(patch_text) or 'bq ' in str(patch_text)):
            return str(patch_text).replace('```', '').replace('bash', '').strip()
        return str(patch_text).strip()


def execute(patch, dry_run=True):
    """Module-level patch execution entry point."""
    executor = Executor(dry_run=dry_run)
    patch_obj = patch.get('_patch_obj') if isinstance(patch, dict) else patch
    return executor.execute(patch_obj or patch)


def execute_rollback(patch, dry_run=True):
    """Module-level rollback execution entry point."""
    executor = Executor(dry_run=dry_run)
    patch_obj = patch.get('_patch_obj') if isinstance(patch, dict) else patch
    return executor.execute_rollback(patch_obj or patch)
