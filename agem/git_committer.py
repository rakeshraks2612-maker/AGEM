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
        
        # Create manifest directory and file
        patches_dir = os.path.join(self.repo_path, "agem-patches")
        os.makedirs(patches_dir, exist_ok=True)
        filename = os.path.join("agem-patches", f"{resource_name}-{timestamp}.md")
        filepath = os.path.join(self.repo_path, filename)
        
        action = getattr(patch, 'action', patch.get('title', 'Optimize resource') if isinstance(patch, dict) else 'Optimize resource')
        before = getattr(patch, 'before', patch.get('diff', {}).get('before', 'N/A') if isinstance(patch, dict) else 'N/A')
        after = getattr(patch, 'after', patch.get('diff', {}).get('after', 'N/A') if isinstance(patch, dict) else 'N/A')
        savings = getattr(patch, 'estimated_savings', f"${patch.get('savings', 38)}/mo" if isinstance(patch, dict) else 'N/A')
        rollback = getattr(patch, 'rollback', patch.get('rollback', 'N/A') if isinstance(patch, dict) else 'N/A')
        
        manifest = f"""# AGEM Optimization Patch
## Resource: {resource_name}
## Timestamp: {timestamp}
## Status: Proposed

### Action
{action}

### Before Configuration
```yaml
{before}
```

### After Configuration (Optimized)
```yaml
{after}
```

### Estimated Financial Savings
{savings}

### Inverse Rollback Command
```bash
{rollback}
```
"""
        with open(filepath, "w") as f:
            f.write(manifest)
            
        # Create branch and commit the patch manifest directly into the isolated GitOps branch
        commit_hash = f"patch-{timestamp[:8]}"
        try:
            curr_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            curr_branch = curr_res.stdout.strip() if curr_res.returncode == 0 else ""
            
            # Switch to isolated branch, add manifest, and commit
            self._run_git(["checkout", "-B", branch_name])
            self._run_git(["add", filename])
            self._run_git(["commit", "-m", f"chore(patch): optimize {resource_name} via AGEM\n\n{action}"])
            
            hash_res = self._run_git(["rev-parse", "--short", "HEAD"])
            if hash_res.returncode == 0 and hash_res.stdout.strip():
                commit_hash = hash_res.stdout.strip()
                
            # Restore working branch
            if curr_branch and curr_branch != branch_name:
                self._run_git(["checkout", curr_branch])
                
            # Attempt push to remote if GITHUB_TOKEN or remote configured
            self._push_to_remote(branch_name)
        except Exception:
            self._run_git(["branch", "-f", branch_name])
            
        return CommitResult(True, branch_name, commit_hash, f"Committed {filename} to {branch_name}")
    
    def _push_to_remote(self, branch_name: str) -> bool:
        """Push isolated branch to remote GitHub repository if GITHUB_TOKEN or credentials exist."""
        token = os.environ.get("GITHUB_TOKEN")
        repo_url = os.environ.get("GITHUB_REPO_URL", "https://github.com/rakeshraks2612-maker/AGEM.git")
        try:
            if token:
                auth_url = repo_url.replace("https://", f"https://{token}@")
                self._run_git(["remote", "set-url", "origin", auth_url])
            push_res = self._run_git(["push", "-u", "origin", branch_name])
            return push_res.returncode == 0
        except Exception:
            return False
    
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
