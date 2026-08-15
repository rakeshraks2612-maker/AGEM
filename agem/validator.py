# agem/validator.py
import re
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class ValidationResult:
    passed: bool
    checks: Dict[str, bool]
    warnings: list
    errors: list


class Validator:
    DANGEROUS_PATTERNS = [
        r"delete\s+", r"DROP\s+", r"rm\s+-rf", r"iam\s+grant", r"set-iam-policy",
    ]
    
    def validate(self, patch: Any, resource: Dict[str, Any], base_cws: float = 0.50, opt_cws: float = 0.20) -> ValidationResult:
        checks = {}
        warnings = []
        errors = []
        
        # 1. Destructive operations check
        after_text = getattr(patch, "after", "") if not isinstance(patch, dict) else patch.get("diff", {}).get("after", "")
        rollback_text = getattr(patch, "rollback", "") if not isinstance(patch, dict) else patch.get("rollback", "")
        savings_text = getattr(patch, "estimated_savings", "") if not isinstance(patch, dict) else str(patch.get("savings", ""))
        
        checks["no_destructive_ops"] = self._check_no_destructive(after_text)
        if not checks["no_destructive_ops"]:
            errors.append("Patch contains potentially destructive operations")
        
        # 2. Rollback presence check
        checks["rollback_present"] = bool(rollback_text and len(rollback_text) > 5)
        if not checks["rollback_present"]:
            warnings.append("No rollback command provided")
        
        # 3. Quantified savings estimate
        checks["savings_estimated"] = bool(savings_text and ("$" in savings_text or any(c.isdigit() for c in savings_text)))
        if not checks["savings_estimated"]:
            warnings.append("No dollar savings estimate provided")
        
        # 4. Score Regression Check: opt_cws MUST be less than base_cws
        checks["no_score_regression"] = (opt_cws < base_cws)
        if not checks["no_score_regression"]:
            errors.append(f"Score regression rejected: proposed CWS ({opt_cws}) >= baseline CWS ({base_cws})")
        
        passed = all(checks.values()) and len(errors) == 0
        return ValidationResult(passed=passed, checks=checks, warnings=warnings, errors=errors)
    
    def _check_no_destructive(self, patch_text: str) -> bool:
        text_lower = patch_text.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower):
                return False
        return True
