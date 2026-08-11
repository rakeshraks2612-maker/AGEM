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
    
    def _extract_command(self, patch_text: str) -> str:
        """Extract gcloud command from patch text."""
        lines = patch_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('gcloud '):
                # Clean up markdown formatting
                return line.replace('```', '').replace('bash', '').strip()
        return ""
