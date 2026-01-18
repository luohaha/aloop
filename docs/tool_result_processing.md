# Tool Result Processing and External Storage

This document describes the intelligent tool result processing and external storage features that help manage large tool outputs and reduce memory pressure.

## Overview

When tools return large outputs (e.g., reading large files, extensive search results), they can quickly consume memory tokens and trigger frequent compression. The tool result processing system addresses this with two strategies:

1. **Intelligent Summarization**: Automatically summarize or truncate large tool results based on tool type
2. **External Storage**: Store very large results externally and keep only summaries in memory

**These features are always enabled** to ensure optimal memory management.

## Configuration

Configure these features in `MemoryConfig`:

```python
from memory.types import MemoryConfig

config = MemoryConfig(
    # Storage threshold
    tool_result_storage_threshold=10000,  # Store externally if > 10k tokens (default)
    tool_result_storage_path="data/tool_results.db",  # SQLite DB path (None = in-memory)

    # Per-tool token budgets
    tool_result_budgets={
        "read_file": 1000,      # Max 1000 tokens for file reads
        "grep_content": 800,    # Max 800 tokens for search results
        "execute_shell": 500,   # Max 500 tokens for shell output
        "web_search": 1200,     # Max 1200 tokens for web searches
        "web_fetch": 1500,      # Max 1500 tokens for web fetches
        "glob_files": 600,      # Max 600 tokens for file listings
        "default": 1000,        # Default for other tools
    }
)
```

## Processing Strategies

Different tools use different processing strategies:

### 1. Extract Key Sections (Code Files)

For `read_file` on code files:
- Extracts imports, class definitions, function definitions
- Omits long comments and repetitive code
- Preserves line numbers for reference

**Example:**
```
[Key sections extracted - 150 lines omitted]

   1: import os
   2: import sys
  10: class MyClass:
  11:     def __init__(self):
  25:     def important_method(self):
  50: def main():

[Use read_file with specific line ranges for full content]
```

### 2. Preserve Matches (Search Results)

For `grep_content`:
- Keeps all matching lines with context
- Preserves file paths and line numbers
- Truncates only if necessary

**Example:**
```
src/main.py:10:def process_data():
src/utils.py:25:def process_data():
src/handlers.py:42:def process_data():

[... 50 more lines omitted. Use more specific search patterns.]
```

### 3. Smart Truncate (General Content)

For `execute_shell`, `web_search`, etc.:
- Keeps first 60% and last 20% of allowed content
- Breaks at line boundaries when possible
- Shows omitted character count

**Example:**
```
Command output starts here...
[first 60% of content]

[... 5000 characters omitted ...]

[last 20% of content]
...command output ends here

[Use more specific queries to see omitted content]
```

### 4. LLM Summarization (Complex Outputs)

For `web_fetch` and other complex outputs:
- Uses a fast model (Haiku) to generate intelligent summaries
- Focuses on information relevant to the task
- Falls back to smart truncate if LLM unavailable

**Example:**
```
[LLM Summary of tool output]

The webpage describes three main features:
1. Authentication using OAuth2
2. REST API with rate limiting
3. WebSocket support for real-time updates

Key endpoints: /api/auth, /api/users, /ws/events

[Full output available via external storage]
```

## External Storage

When tool results exceed the storage threshold (default: 10,000 tokens), they are stored externally:

### Storage Flow

1. **Tool executes** → Returns large result
2. **Processor evaluates** → Determines result is too large
3. **Store externally** → Saves full content to SQLite
4. **Return reference** → Memory gets summary + reference ID

### Reference Format

```
[Tool Result #read_file_a1b2c3d4]
Tool: read_file
Size: 50000 chars (~14285 tokens)
Stored: 2026-01-17 10:30:00

Summary:
[Processed summary of the content]

[Full content available via retrieve_tool_result tool - use this ID to access]
```

### Retrieving Stored Results

The agent automatically gets a `retrieve_tool_result` tool when external storage is enabled:

```python
# Agent can call this tool to retrieve full content
retrieve_tool_result(result_id="read_file_a1b2c3d4")
```

**Tool description:**
```
Retrieve the full content of a tool result that was stored externally.
Use this when you see a '[Tool Result #...]' reference in the conversation
and need to access the complete output.
```

## Usage Examples

### Example 1: Reading a Large File

```python
# Without processing (old behavior)
result = read_file("large_file.py")  # 20,000 chars
# → Entire file added to memory (5,700 tokens)
# → Triggers compression

# With processing (new behavior)
result = read_file("large_file.py")  # 20,000 chars
# → Key sections extracted (1,000 tokens)
# → No compression needed
```

### Example 2: External Storage

```python
# Very large file
result = read_file("huge_log.txt")  # 100,000 chars (28,500 tokens)

# Result in memory:
"""
[Tool Result #read_file_xyz789]
Tool: read_file
Size: 100000 chars (~28571 tokens)

Summary:
Log file contains 5000 entries from 2026-01-15 to 2026-01-17.
Main events: 3000 INFO, 1500 WARNING, 500 ERROR.
Most common errors: ConnectionTimeout (200), AuthFailure (150).

[Full content available via retrieve_tool_result tool]
"""
# → Only ~200 tokens in memory instead of 28,500!

# Later, if agent needs full content:
full_content = retrieve_tool_result("read_file_xyz789")
```

### Example 3: Grep Results

```python
# Search returns many matches
result = grep_content(pattern="TODO", path="src/")
# → 500 matches found

# Processed result:
"""
src/main.py:10:# TODO: Refactor this
src/main.py:25:# TODO: Add error handling
src/utils.py:15:# TODO: Optimize performance
...
[First 50 matches shown]

[... 450 more lines omitted. Use more specific search patterns.]
"""
# → Reduced from 2,000 tokens to 800 tokens
```

## Benefits

### Memory Efficiency

- **Reduced token usage**: 50-90% reduction for large tool results
- **Less frequent compression**: Fewer compression cycles needed
- **Better context quality**: More room for important information

### Performance

- **Faster processing**: Less data to compress
- **Lower costs**: Fewer tokens sent to LLM
- **Scalable**: Can handle very large tool outputs

### Flexibility

- **Configurable**: Adjust budgets per tool type
- **Retrievable**: Full content available when needed
- **Transparent**: Agent knows when content is truncated/stored

## Monitoring

### Check Processing Stats

```python
# Get memory stats including tool result processing
stats = agent.memory.get_stats()
print(f"Tool results stored: {stats['tool_result_stats']['total_results']}")
print(f"Total tokens saved: {stats['tool_result_stats']['total_tokens']}")
```

### Check Storage Stats

```python
# Get external storage statistics
storage_stats = agent.memory.get_tool_result_stats()
print(f"Stored results: {storage_stats['total_results']}")
print(f"Total size: {storage_stats['total_bytes']} bytes")
print(f"Average access count: {storage_stats['avg_access_count']}")
```

## Advanced Configuration

### Custom Tool Budgets

```python
config = MemoryConfig(
    tool_result_budgets={
        "read_file": 1500,      # Allow more tokens for code files
        "grep_content": 500,    # Restrict search results more
        "my_custom_tool": 2000, # Custom tool budget
    }
)
```

### Disable for Specific Scenarios

```python
# Disable processing for critical tasks where full content is needed
config = MemoryConfig(
    enable_tool_result_processing=False,  # Keep all content
    enable_tool_result_storage=False,     # No external storage
)
```

### Persistent Storage

```python
# Use persistent database for tool results
config = MemoryConfig(
    tool_result_storage_path="data/tool_results.db",  # Persistent
)

# Or use in-memory (default)
config = MemoryConfig(
    tool_result_storage_path=None,  # In-memory only
)
```

## Cleanup

External storage can be cleaned up periodically:

```python
# Remove results older than 7 days
deleted = agent.memory.tool_result_store.cleanup_old_results(days=7)
print(f"Cleaned up {deleted} old results")
```

## Implementation Details

### Architecture

```
Tool Execution
    ↓
Raw Result (may be large)
    ↓
ToolResultProcessor.process_result()
    ├─ Small result → Pass through
    ├─ Medium result → Summarize/truncate
    └─ Large result → Recommend external storage
    ↓
MemoryManager.process_tool_result()
    ├─ Apply processing
    └─ Store externally if needed
    ↓
Processed Result (optimized for memory)
    ↓
Add to Memory
```

### Files

- `memory/tool_result_processor.py` - Processing strategies
- `memory/tool_result_store.py` - External storage (SQLite)
- `memory/manager.py` - Integration with memory system
- `agent/base.py` - Integration with agent execution
- `tools/retrieve_tool_result.py` - Retrieval tool

### Database Schema

```sql
CREATE TABLE tool_results (
    id TEXT PRIMARY KEY,              -- Hash-based ID
    tool_call_id TEXT NOT NULL,       -- Original tool call ID
    tool_name TEXT NOT NULL,          -- Tool that produced result
    content TEXT NOT NULL,            -- Full content
    content_hash TEXT NOT NULL,       -- SHA256 hash (deduplication)
    summary TEXT,                     -- Processed summary
    token_count INTEGER,              -- Estimated tokens
    created_at TIMESTAMP NOT NULL,    -- Creation time
    accessed_at TIMESTAMP,            -- Last access time
    access_count INTEGER DEFAULT 0    -- Number of retrievals
);
```

## Best Practices

1. **Set appropriate budgets**: Balance between context quality and memory usage
2. **Use persistent storage**: For long-running sessions or when results need to persist
3. **Monitor stats**: Check processing effectiveness regularly
4. **Clean up old results**: Prevent database bloat
5. **Test with your workload**: Adjust budgets based on your specific use case

## Troubleshooting

### Issue: Results still too large

**Solution**: Lower the tool-specific budget:
```python
config.tool_result_budgets["read_file"] = 500  # Reduce from 1000
```

### Issue: Important information lost

**Solution**: Increase budget for specific tools:
```python
config.tool_result_budgets["my_tool"] = 2000  # Increase budget
```

### Issue: External storage not working

**Solution**: Check configuration and permissions:
```python
# Check database path is writable
import os
db_dir = os.path.dirname(config.tool_result_storage_path or "data/tool_results.db")
assert os.access(db_dir, os.W_OK)
```

### Issue: Agent can't retrieve stored results

**Solution**: The retrieve_tool_result tool is automatically registered and always available.

## See Also

- [Memory Management](memory-management.md) - Overall memory system
- [Memory Persistence](memory_persistence.md) - Session persistence
- [Configuration](configuration.md) - Full configuration options
