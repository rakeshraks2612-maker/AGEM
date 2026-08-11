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
    
    def validate(self, patch: Any, resource: Dict[str, Any]) -> ValidationResult:
        checks = {}
        warnings = []
        errors = []
        
        checks["no_destructive_ops"] = self._check_no_destructive(patch.after)
        if not checks["no_destructive_ops"]:
            errors.append("Patch contains potentially destructive operations")
        
        checks["rollback_present"] = bool(patch.rollback and len(patch.rollback) > 10)
        if not checks["rollback_present"]:
            warnings.append("No rollback command provided")
        
        checks["savings_estimated"] = bool(patch.estimated_savings and "$" in patch.estimated_savings)
        if not checks["savings_estimated"]:
            warnings.append("No dollar savings estimate provided")
        
        passed = all(checks.values()) and len(errors) == 0
        return ValidationResult(passed=passed, checks=checks, warnings=warnings, errors=errors)
    
    def _check_no_destructive(self, patch_text: str) -> bool:
        text_lower = patch_text.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower):
                return False
        return True
