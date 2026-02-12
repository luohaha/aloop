"""Role system for specialized agent personas."""

from .manager import RoleManager
from .types import MemoryOverrides, RoleConfig, SkillsConfig, VerificationConfig

__all__ = [
    "MemoryOverrides",
    "RoleConfig",
    "RoleManager",
    "SkillsConfig",
    "VerificationConfig",
]
