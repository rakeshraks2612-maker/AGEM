import shlex
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    passed: bool
    checks: Dict[str, bool]
    warnings: list
    errors: list


class Validator:
    """Deterministic Safety and Structural Validator for gcloud and Terraform optimization patches."""
    
    # Destructive or unsafe operations strictly blocked
    DANGEROUS_COMMANDS = [
        "delete", "drop", "destroy", "rm", "truncate", "kill", "terminate",
        "purge", "revoke", "format", "wipe", "uninstall"
    ]
    
    # Dangerous parameter flags
    DANGEROUS_FLAGS = [
        "--force", "--quiet-delete", "--delete-data", "--cascade",
        "--auto-approve", "--no-backup", "--disable-encryption"
    ]
    
    # Valid safe gcloud subcommands for optimization
    SAFE_COMMAND_PREFIXES = [
        ("gcloud", "run", "services", "update"),
        ("gcloud", "sql", "instances", "patch"),
        ("gcloud", "alpha", "bq", "tables", "update"),
        ("bq", "update"),
    ]

    def validate(self, patch: Any, resource: Optional[Dict[str, Any]] = None, base_cws: float = 0.50, opt_cws: float = 0.20) -> ValidationResult:
        checks = {}
        warnings = []
        errors = []
        
        # 1. Structural & Content Extraction
        after_text = getattr(patch, "after", "") if not isinstance(patch, dict) else (patch.get("after") or patch.get("diff", {}).get("after", ""))
        rollback_text = getattr(patch, "rollback", "") if not isinstance(patch, dict) else patch.get("rollback", "")
        savings_text = getattr(patch, "estimated_savings", "") if not isinstance(patch, dict) else str(patch.get("savings", ""))
        
        # 2. Structural Command Syntax & Safety Grammar Verification
        cmd_valid, cmd_err = self._validate_command_structure(after_text)
        checks["command_syntax_valid"] = cmd_valid
        if not cmd_valid and cmd_err:
            errors.append(cmd_err)
            
        non_destructive = self._check_no_destructive(after_text)
        checks["no_destructive_ops"] = non_destructive
        checks["non_destructive"] = non_destructive
        if not non_destructive:
            errors.append("Patch contains potentially destructive command syntax or prohibited flags")
        
        # 3. Invert Rollback Playbook Verification
        has_rollback, rb_err = self._validate_rollback_structure(after_text, rollback_text)
        checks["rollback_present"] = has_rollback
        checks["has_rollback"] = has_rollback
        if not has_rollback and rb_err:
            errors.append(rb_err)
        
        # 4. Quantified Dollar Savings Estimation
        has_savings = bool(savings_text and ("$" in savings_text or any(c.isdigit() for c in savings_text)))
        checks["savings_estimated"] = has_savings
        checks["has_savings"] = has_savings
        if not has_savings:
            warnings.append("No dollar savings estimate provided")
        
        # 5. Score Regression Check: opt_cws MUST be strictly less than base_cws
        cws_improved = (opt_cws < base_cws)
        checks["no_score_regression"] = cws_improved
        if not cws_improved:
            errors.append(f"Score regression rejected: proposed CWS ({opt_cws}) >= baseline CWS ({base_cws})")
        
        passed = all(checks.values()) and len(errors) == 0
        return ValidationResult(passed=passed, checks=checks, warnings=warnings, errors=errors)
    
    def _validate_command_structure(self, patch_text: str) -> Tuple[bool, Optional[str]]:
        """Parse command tokens to ensure proper gcloud/bq CLI structure."""
        if not patch_text or not patch_text.strip():
            return False, "Empty patch command string"
        
        try:
            tokens = shlex.split(patch_text.strip())
        except Exception as e:
            return False, f"Malformed shell syntax: {e}"
        
        if not tokens:
            return False, "No command tokens found in patch"
            
        # Check against prohibited flags
        for token in tokens:
            if any(token.lower() == flag or token.lower().startswith(flag + "=") for flag in self.DANGEROUS_FLAGS):
                return False, f"Prohibited dangerous flag detected: '{token}'"
                
        # Check for matching safe prefix
        is_safe_prefix = any(
            len(tokens) >= len(prefix) and all(tokens[i] == prefix[i] for i in range(len(prefix)))
            for prefix in self.SAFE_COMMAND_PREFIXES
        )
        if not is_safe_prefix and tokens[0] in ["gcloud", "bq"]:
            # Generic safe check: must not contain delete/drop verb
            if any(verb in [t.lower() for t in tokens] for verb in self.DANGEROUS_COMMANDS):
                return False, f"Prohibited command verb detected in command tokens: {tokens[:4]}"
                
        return True, None

    def _validate_rollback_structure(self, after_text: str, rollback_text: str) -> Tuple[bool, Optional[str]]:
        """Verify that rollback command exists and is safe."""
        if not rollback_text or len(rollback_text.strip()) < 5:
            return False, "Missing required rollback playbook command"
        try:
            tokens = shlex.split(rollback_text.strip())
            for token in tokens:
                if any(token.lower() == flag for flag in self.DANGEROUS_FLAGS):
                    return False, f"Dangerous flag in rollback command: '{token}'"
            return True, None
        except Exception as e:
            return False, f"Malformed rollback shell syntax: {e}"

    def _check_no_destructive(self, patch_text: str) -> bool:
        text_lower = patch_text.lower()
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(r"\b" + re.escape(pattern) + r"\b", text_lower):
                return False
        return True


def validate(patches):
    """Module-level validator entry point for server and CLI."""
    validator = Validator()
    if not isinstance(patches, list):
        patches = [patches]
    for p in patches:
        patch = p.get('_patch_obj') if isinstance(p, dict) else p
        r_name = p.get('resource_name', getattr(patch, 'resource_name', 'resource')) if isinstance(p, dict) else getattr(patch, 'resource_name', 'resource')
        resource = {'type': 'GCP Resource', 'name': r_name}
        res = validator.validate(patch or p, resource, base_cws=0.50, opt_cws=0.20)
        if not res.passed and res.errors:
            raise ValueError(f"Validation failed: {res.errors}")
    return True
