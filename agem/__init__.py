"""AGEM (Autonomous Google-powered Efficiency Manager) package."""

from agem import profiler
from agem import scorer
from agem import patcher
from agem import validator
from agem import git_committer
from agem import executor
from agem import state_manager

__version__ = "2.6.3"

__all__ = [
    "profiler",
    "scorer",
    "patcher",
    "validator",
    "git_committer",
    "executor",
    "state_manager",
]
