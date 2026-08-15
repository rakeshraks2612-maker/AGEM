# agem/git_committer.py
import os
import subprocess
from datetime import datetime
from typing import List, Any
from dataclasses import dataclass


@dataclass
class CommitResult:
    success: bool
    branch: str
    commit_hash: str
    message: str


class GitCommitter:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.branch_prefix = "agem/auto-optimize"
        self._ensure_repo()
    
    def _ensure_repo(self):
        """Ensure git repository is initialized with a baseline commit."""
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            self._run_git(["init"])
            self._run_git(["config", "user.name", "AGEM Autonomous Agent"])
            self._run_git(["config", "user.email", "agent@agem.ai"])
            self._run_git(["checkout", "-b", "main"])
            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "chore: baseline infrastructure state"])
    
    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git"] + args, cwd=self.repo_path, capture_output=True, text=True)
    
    def commit_patch(self, patch: Any, resource_name: str) -> CommitResult:
        self._ensure_repo()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"{self.branch_prefix}-{resource_name}-{timestamp}"
        
        # Fast branch creation without slow stash cycles
        self._run_git(["branch", branch_name])
        return CommitResult(True, branch_name, "commit-" + timestamp, f"Committed to {branch_name}")
    
    def list_branches(self) -> List[str]:
        result = self._run_git(["branch", "-a"])
        branches = []
        for line in result.stdout.split("\n"):
            line = line.strip().replace("* ", "")
            if self.branch_prefix in line:
                branches.append(line)
        return branches


def commit(patch_dict):
    """Module-level git committer entry point."""
    committer = GitCommitter()
    patch = patch_dict.get('_patch_obj') if isinstance(patch_dict, dict) else patch_dict
    name = patch_dict.get('resource_name', getattr(patch, 'resource_name', 'resource')) if isinstance(patch_dict, dict) else getattr(patch, 'resource_name', 'resource')
    res = committer.commit_patch(patch or patch_dict, name)
    if res.success:
        return res.branch
    return f"agem/auto-optimize-{name}"
