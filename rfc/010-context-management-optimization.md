# RFC 010: Context Management Optimization

## Problem Statement

The current memory compression system is reactive and coarse:

1. **Silent eviction via deque**: `ShortTermMemory` uses `deque(maxlen=N)` which silently drops the oldest message when capacity is reached. This can break `tool_use`/`tool_result` pairs, causing API errors. The message-count compression trigger (`is_full()`) exists solely to prevent this, but it's a workaround, not a fix.

2. **Inaccurate token estimation**: For Anthropic/Gemini, token counting uses character estimation (~3.5-4 chars/token) which can be off by 20-30%. Meanwhile, actual token counts from `response.usage` are available after every API call but aren't used for compression decisions.

3. **No message differentiation**: All messages are treated equally during compression. Tool results (re-obtainable facts like file contents) and LLM reasoning (expensive to regenerate) get the same treatment, leading to suboptimal context preservation.

4. **Sawtooth compression pattern**: Compression happens as one big batch at threshold, losing significant context at once. A progressive approach (partial compression at a soft threshold, full at hard) would smooth the curve and preserve more useful context.

## Design Goals

- **Eliminate silent eviction** — no data loss without explicit compression
- **Ground compression decisions in API-reported token counts** when available
- **Preserve high-value context** (reasoning, decisions) over low-value (raw tool output)
- **Smooth compression** via soft/hard thresholds instead of all-or-nothing

## Proposed Approach

### 1. ShortTermMemory: deque → list

Replace `deque(maxlen=N)` with a plain `list`. The `max_size` parameter becomes an emergency cap (default 500) that only triggers compression as a safety net. No messages are ever silently dropped.

### 2. API-Grounded Token Tracking

Add `_last_api_context_tokens` field to `MemoryManager`. When `actual_tokens` is provided (after API calls), use that as the authoritative token count. Between API calls, estimate only the delta (new user/tool messages). Fall back to full estimation only before the first API call.

### 3. Remove Message-Count Compression Trigger

With deque eviction gone, the `short_term.is_full()` trigger is no longer needed for safety. Keep only:
- Hard limit: `current_tokens > MEMORY_COMPRESSION_THRESHOLD`
- Emergency cap: `short_term.count() >= 500` (safety net for broken token counting)

### 4. Structured Memory Classification

At compression time, classify messages into categories:
- **INSTRUCTION**: system messages, user text requests
- **REASONING**: assistant analysis/planning
- **FACT**: tool results, tool_result blocks
- **MIXED**: assistant with tool_calls

Compress FACTs first (they can be re-obtained), preserve REASONING and INSTRUCTION longer. Update the compression prompt to prioritize preserving reasoning chains and decisions.

### 5. Progressive Compression (Soft/Hard Threshold)

Introduce urgency levels:
- **SOFT** (60% of hard limit): compress only the oldest portion of messages
- **HARD** (at limit): full compression (existing behavior)
- **EMERGENCY** (message count cap): full compression as safety net

Soft compression finds a safe split point that doesn't break tool pairs, then compresses only the first half.

## Alternatives Considered

- **Streaming compression**: Compress each message as it arrives. Rejected because LLM summarization calls are expensive and the per-message overhead would be prohibitive.
- **Token-budget partitioning**: Reserve fixed budgets for system/tools/conversation. Rejected as too rigid — the optimal split depends on the task.
- **Keep deque with larger size**: Doesn't solve the fundamental silent eviction problem and masks bugs.

## Risks

- **Token estimation drift**: Between API calls, estimated deltas could drift. Mitigated by resetting to actual counts on every API response.
- **Classification heuristics**: Simple role-based classification may miscategorize some messages. Acceptable because the impact is compression ordering, not data loss.
- **Soft compression overhead**: Extra LLM call for partial compression. Mitigated by only triggering when actually needed (60% threshold).
