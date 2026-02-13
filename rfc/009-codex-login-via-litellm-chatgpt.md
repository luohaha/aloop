# RFC: Codex Login via LiteLLM ChatGPT Provider

Status: **Proposed**

## Problem Statement

ouro currently requires static API keys in `~/.ouro/models.yaml`. This blocks users who want to use ChatGPT Plus/Pro Codex subscription credentials (OAuth/device flow) instead of API keys.

We need a way to authenticate and run Codex-capable models without introducing a large new provider stack.

## Design Goals

1. **Minimal surface change**: Add login/logout/status UX without refactoring the agent core.
2. **Reuse existing transport**: Keep using `LiteLLMAdapter` for request/response conversion, usage extraction, and retries.
3. **Subscription auth support**: Enable ChatGPT/Codex OAuth login flow.
4. **Runtime directory consistency**: Store credentials under `~/.ouro` instead of tool-specific default locations.
5. **Forward compatibility**: Keep room for a dedicated `CodexAdapter` later if LiteLLM behavior regresses.

## Constraints

- The repository is async-first in runtime code; interactive command handlers must avoid blocking the event loop.
- `main.py` remains the CLI entrypoint and can own synchronous flow when appropriate.
- Existing model configuration format should remain YAML-first.

## Proposed Approach

### 1. Raise LiteLLM minimum version

Update dependency from `litellm>=1.30.0` to `litellm>=1.81.1,<2.0`.

Rationale: ChatGPT subscription provider support (`chatgpt/*`) appears in LiteLLM 1.81.1+.

### 2. Add ChatGPT auth helper module

Add `llm/chatgpt_auth.py` to:
- set/normalize `CHATGPT_TOKEN_DIR` to `~/.ouro/auth/chatgpt`
- trigger login via LiteLLM ChatGPT authenticator
- remove local auth file for logout
- inspect auth status (present/expired/account id)

### 3. Add CLI and interactive auth commands

CLI:
- `--login` (open provider selector, then login)
- `--logout` (open provider selector, then logout)

Interactive:
- `/login` (open provider selector)
- `/logout` (open provider selector)
- `/auth`

### 4. Allow chatgpt models without API keys

Update `ModelManager.validate_model()` so provider `chatgpt` does not require `api_key` in `models.yaml`.

Example model config:

```yaml
models:
  chatgpt/gpt-5.2-codex:
    timeout: 600

default: chatgpt/gpt-5.2-codex
```

## Alternatives Considered

### A) Implement dedicated `CodexAdapter` now

Pros:
- Full control over request/stream parsing and headers.

Cons:
- Re-implements behavior LiteLLM already ships (responses bridge, usage conversion, auth refresh).
- Larger maintenance burden and more test surface.

Decision: defer until LiteLLM route proves insufficient.

### B) Keep LiteLLM default token dir (`~/.config/litellm/chatgpt`)

Pros:
- Zero extra helper logic.

Cons:
- Splits ouro runtime state across directories.

Decision: set token dir to `~/.ouro/auth/chatgpt`.

## Risks

1. **Upstream behavior drift** in LiteLLM chatgpt provider.
2. **Prompt layering differences** if provider injects additional instructions.
3. **OAuth UX differences** across terminals/platforms.

Mitigations:
- keep auth integration encapsulated in helper module
- preserve existing adapter abstraction for future fallback
- document explicit login flow and troubleshooting

## Success Criteria

- Users can run `chatgpt/*` models in ouro without API key fields.
- `--login`, `--logout`, `/login`, `/logout`, `/auth` function end-to-end.
- Existing token/cost tracking remains available via existing LiteLLM usage path.
- Documentation clearly explains setup and commands.
