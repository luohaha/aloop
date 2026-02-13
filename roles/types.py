"""Data types for the role system."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MemoryOverrides:
    """Optional memory configuration overrides for a role."""

    short_term_size: int | None = None
    compression_threshold: int | None = None
    compression_ratio: float | None = None
    strategy: str | None = None  # sliding_window | selective | deletion
    long_term_memory: bool | None = None


@dataclass(frozen=True)
class SkillsConfig:
    """Skills configuration for a role."""

    enabled: bool = True
    allowed: list[str] | None = None  # None = all skills


@dataclass(frozen=True)
class VerificationConfig:
    """Verification (ralph loop) configuration for a role."""

    enabled: bool = True
    max_iterations: int = 3


@dataclass(frozen=True)
class RoleConfig:
    """Complete configuration for an agent role."""

    name: str
    description: str
    system_prompt: str | None = None  # None = use full LoopAgent.SYSTEM_PROMPT
    tools: list[str] | None = None  # None = all tools
    guidelines: list[str] | None = None  # Optional usage guidelines appended to prompt
    agents_md: bool = True
    memory: MemoryOverrides = field(default_factory=MemoryOverrides)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    source_path: Path | None = None
