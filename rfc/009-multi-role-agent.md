# RFC 009: Multi-Role Agent System

## Status

Implemented

## Summary

Support multiple "roles" — specialized agent personas with focused tool sets, custom system prompts, and tuned memory strategies. Roles are defined as YAML files, so adding or modifying roles requires no code changes. A role is selected at startup via `ouro --role <name>` (default: `general`, which preserves current behavior exactly).

## Problem Statement

ouro has a single unified agent with a fixed system prompt, all tools always loaded, and global memory configuration. This creates several issues:

1. **Context waste**: A research-only session loads editing/shell tools the agent never uses, and system prompt sections (task management, complex strategy) that add noise.
2. **No specialization**: The same generic persona handles coding, web research, and debugging, with no way to tune behavior per use case.
3. **Rigid memory**: Some tasks need aggressive compression (long research sessions) while others benefit from full context retention. There's no per-task tuning.
4. **Feature coupling**: Skills, verification (ralph loop), long-term memory, and AGENTS.md discovery are always-on. Roles that don't need them pay the cost anyway.

## Design Goals

- **Zero regression**: `ouro` (no `--role`) behaves identically to before — the `general` role maps to the existing system prompt, all tools, and all features.
- **Composition over inheritance**: Role YAML defines persona/instructions; infrastructure sections (AGENTS.md, task management, tool guidelines) are conditionally appended based on the role's tool set and config flags.
- **YAML-only extension**: Users create `~/.ouro/roles/foo.yaml` to add a role. No Python code needed.
- **Startup-only**: Role is immutable after startup. No runtime switching — keeps the system simple and avoids mid-session prompt/tool inconsistencies.

## Design

### Role YAML Format

```yaml
name: searcher
description: Web search and research specialist

system_prompt: |
  <role>
  You are a web research specialist. Search the web and synthesize information.
  Always cite sources. Prefer authoritative sources.
  </role>

# Tool whitelist (omit or null = all tools)
tools:
  - web_search
  - web_fetch
  - read_file
  - glob_files
  - grep_content

# Whether to include <agents_md> section (default: true)
agents_md: false

# Memory overrides (all optional, defaults from Config)
memory:
  short_term_size: 50
  compression_threshold: 30000
  compression_ratio: 0.3
  strategy: sliding_window
  long_term_memory: false

# Skills (default: enabled)
skills:
  enabled: false

# Verification / ralph loop (default: enabled)
verification:
  enabled: false
```

### Auto-Composition Rules

| Condition | Effect |
|-----------|--------|
| `system_prompt: null` | Full `LoopAgent.SYSTEM_PROMPT` (all sections) |
| `system_prompt:` set | Role prompt + conditional infrastructure sections |
| `manage_todo_list` in tools | `<task_management>` section auto-included |
| `agents_md: true` | `<agents_md>` section included |
| Always | `<tool_usage_guidelines>` + `<workflow>` included |

### Loading Order

1. Built-in roles from `roles/builtin/*.yaml` (shipped with the package)
2. User roles from `~/.ouro/roles/*.yaml`
3. User roles override built-in roles of the same name
4. `general` is guaranteed to exist (fallback created if no YAML found)

### Architecture

#### Phase 0: Internal Modularization (prerequisite)

Three refactors that enable role composition without changing behavior:

1. **Tool Registry** (`tools/registry.py`): Centralizes tool creation. `CORE_TOOLS` dict maps names to classes; `create_core_tools(names)` creates filtered subsets. Agent-dependent tools (`ExploreTool`, `ParallelExecutionTool`) added separately via `add_agent_tools()`.

2. **System Prompt Sections** (`agent/agent.py`): Splits monolithic `SYSTEM_PROMPT` into named constants (`PROMPT_ROLE`, `PROMPT_CRITICAL_RULES`, `PROMPT_AGENTS_MD`, `PROMPT_TASK_MANAGEMENT`, `PROMPT_TOOL_GUIDELINES`, `PROMPT_WORKFLOW`, `PROMPT_COMPLEX_STRATEGY`). Full prompt preserved as join of all sections.

3. **Memory Config Injection** (`memory/manager.py`): `MemoryManager.__init__()` accepts optional overrides (`short_term_size`, `compression_threshold`, `compression_ratio`, `compression_strategy`, `long_term_memory`). All `Config.MEMORY_*` references replaced with instance attributes. Backward compatible — unset overrides fall through to `Config` defaults.

#### Phase 1: Role System

New `roles/` package:

```
roles/
  __init__.py          # Exports: RoleManager, RoleConfig
  types.py             # RoleConfig, MemoryOverrides, SkillsConfig, VerificationConfig
  manager.py           # RoleManager (load, parse, get)
  builtin/             # Built-in YAML files (not a Python package)
    general.yaml
    searcher.yaml
    debugger.yaml
    coder.yaml
```

Integration points:

- `BaseAgent.__init__()` accepts `role`, conditionally adds `TodoTool`, passes memory overrides
- `LoopAgent._build_system_prompt()` composes prompt per role
- `LoopAgent.run()` respects `role.verification.enabled` and `role.verification.max_iterations`
- `main.py` adds `--role` CLI flag, filters tools via registry, conditional skills loading
- `interactive.py` shows role name in startup banner

## Key Decisions

1. **`general` = current behavior**: No `--role` flag → `general` role → `system_prompt=None` → full `SYSTEM_PROMPT`, all tools, all features. Zero change for existing users.

2. **TodoTool ↔ task_management**: `manage_todo_list` in the role's tool list auto-includes the `<task_management>` prompt section. Not in tool list → excluded from both tools and prompt. No separate flag needed.

3. **`agents_md` is a separate boolean**: Some roles want AGENTS.md discovery (e.g., debugger in a project) but not TodoTool. Kept as a standalone config.

4. **Memory strategy override**: `memory.strategy` sets a preferred compression strategy. `MemoryManager._select_strategy()` returns it directly, bypassing auto-selection.

5. **Global scope only**: Roles live in `~/.ouro/roles/` (user) and `roles/builtin/` (shipped). No per-project roles — keeps discovery simple.

6. **No runtime switching**: Role is immutable after startup. Avoids mid-session prompt/tool/memory inconsistencies.

## Built-in Roles

| Role | Tools | Verification | LTM | Skills | Use Case |
|------|-------|-------------|-----|--------|----------|
| `general` | All | On | On | On | Default, all-purpose |
| `searcher` | Web + read/glob/grep | Off | Off | Off | Research, information gathering |
| `debugger` | Read/glob/grep/shell | Off | Off | Off | Investigation, root cause analysis |
| `coder` | All | On | On | On | Full coding with verification |

## Alternatives Considered

1. **Config file flags** (e.g., `TOOLS_ENABLED=read_file,shell`): Too rigid, no persona customization, clutters the global config.

2. **Runtime role switching** (`/role searcher`): Adds complexity (prompt rebuild, tool hot-swap, memory state questions). Deferred — startup-only is simpler and covers the primary use case.

3. **Per-project roles** (`.ouro/roles/`): Useful but adds discovery complexity. Can be added later without breaking changes.

4. **Role inheritance** (`extends: general`): Over-engineering for MVP. Composition (role prompt + conditional sections) covers the same need more simply.

## Future Work

- Per-project roles (`.ouro/roles/*.yaml` in project root)
- Role inheritance / `extends` field
- `/roles` command to list available roles in interactive mode
- Role-specific tool configuration (e.g., shell timeout overrides)
- MCP server integration per role
