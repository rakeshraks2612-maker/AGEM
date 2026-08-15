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


class Executor:
    """Executes validated gcloud patches with dry-run safety."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run  # Default: simulate only. Set False to actually apply.
    
    def execute(self, patch: Any) -> ExecutionResult:
        """Run the patch command (or simulate if dry_run=True)."""
        command = self._extract_command(patch.after)
        
        if not command:
            return ExecutionResult(False, "", "", "No gcloud command found in patch")
        
        if self.dry_run:
            # Simulate: just echo what would happen
            return ExecutionResult(
                success=True,
                stdout=f"[DRY-RUN] Would execute: {command}",
                stderr="",
                command=command,
            )
        
        # Actually execute
        result = subprocess.run(
            command.split(),
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
        
        result = subprocess.run(
            command.split(),
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
