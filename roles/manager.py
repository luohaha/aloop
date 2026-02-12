"""Role manager: loads, parses, and provides role configurations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .types import MemoryOverrides, RoleConfig, SkillsConfig, VerificationConfig

logger = logging.getLogger(__name__)

BUILTIN_ROLES_DIR = Path(__file__).parent / "builtin"
USER_ROLES_DIR = Path.home() / ".ouro" / "roles"


class RoleManager:
    """Manages loading and lookup of role configurations."""

    def __init__(self) -> None:
        self.roles: dict[str, RoleConfig] = {}
        self._load()

    def _load(self) -> None:
        """Load roles from builtin and user directories."""
        builtin = self._load_from_dir(BUILTIN_ROLES_DIR)
        user = self._load_from_dir(USER_ROLES_DIR)
        # User roles override builtin roles of the same name
        self.roles = {**builtin, **user}
        # Ensure 'general' always exists
        if "general" not in self.roles:
            self.roles["general"] = self._create_general_role()

    def _load_from_dir(self, directory: Path) -> dict[str, RoleConfig]:
        """Load all YAML role files from a directory.

        Args:
            directory: Path to scan for *.yaml files.

        Returns:
            Dict mapping role name to RoleConfig.
        """
        roles: dict[str, RoleConfig] = {}
        if not directory.is_dir():
            return roles

        for yaml_path in sorted(directory.glob("*.yaml")):
            role = self._try_parse_yaml(yaml_path)
            if role:
                roles[role.name] = role

        return roles

    def _try_parse_yaml(self, path: Path) -> RoleConfig | None:
        """Try to parse a YAML file, returning None on failure."""
        try:
            return self._parse_yaml(path)
        except Exception:
            logger.warning(f"Skipping malformed role file: {path}", exc_info=True)
            return None

    def _parse_yaml(self, path: Path) -> RoleConfig | None:
        """Parse a single YAML file into a RoleConfig.

        Args:
            path: Path to the YAML file.

        Returns:
            RoleConfig or None if the file is invalid.
        """
        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        name = data.get("name")
        if not name:
            logger.warning(f"Role file missing 'name': {path}")
            return None

        description = data.get("description", "")

        # Parse memory overrides
        mem_data = data.get("memory") or {}
        memory = MemoryOverrides(
            short_term_size=mem_data.get("short_term_size"),
            compression_threshold=mem_data.get("compression_threshold"),
            compression_ratio=mem_data.get("compression_ratio"),
            strategy=mem_data.get("strategy"),
            long_term_memory=mem_data.get("long_term_memory"),
        )

        # Parse skills config
        skills_data = data.get("skills")
        if skills_data is not None:
            skills = SkillsConfig(
                enabled=skills_data.get("enabled", True),
                allowed=skills_data.get("allowed"),
            )
        else:
            skills = SkillsConfig()

        # Parse verification config
        verify_data = data.get("verification")
        if verify_data is not None:
            verification = VerificationConfig(
                enabled=verify_data.get("enabled", True),
                max_iterations=verify_data.get("max_iterations", 3),
            )
        else:
            verification = VerificationConfig()

        return RoleConfig(
            name=name,
            description=description,
            system_prompt=data.get("system_prompt"),
            tools=data.get("tools"),
            agents_md=data.get("agents_md", True),
            memory=memory,
            skills=skills,
            verification=verification,
            source_path=path,
        )

    @staticmethod
    def _create_general_role() -> RoleConfig:
        """Create the default 'general' role (all tools, full prompt)."""
        return RoleConfig(
            name="general",
            description="General-purpose assistant with all tools and features enabled",
        )

    def get_role(self, name: str) -> RoleConfig | None:
        """Get a role by name.

        Args:
            name: Role name.

        Returns:
            RoleConfig or None if not found.
        """
        return self.roles.get(name)

    def list_roles(self) -> list[RoleConfig]:
        """List all available roles."""
        return list(self.roles.values())

    def get_role_names(self) -> list[str]:
        """Return all available role names."""
        return list(self.roles.keys())
