# Memory Module Tests

Comprehensive unit tests for the memory management system.

## Test Structure

```
test/memory/
├── __init__.py                 # Package initialization
├── conftest.py                 # Pytest fixtures and mock objects
├── test_memory_manager.py      # MemoryManager tests
├── test_compressor.py          # WorkingMemoryCompressor tests
├── test_short_term.py          # ShortTermMemory tests
├── test_integration.py         # Integration tests
└── README.md                   # This file
```

## Test Coverage

### 1. Memory Manager Tests (`test_memory_manager.py`)
- **Basic functionality**: initialization, adding messages, context retrieval
- **Compression triggering**: soft limit, hard limit, short-term full
- **Tool call/result matching**: Critical tests for the tool pair matching issue
- **Protected tools**: Tests for protected tool handling
- **Edge cases**: empty compression, single message, actual token counts

### 2. Compressor Tests (`test_compressor.py`)
- **Compression strategies**: SLIDING_WINDOW, DELETION, SELECTIVE
- **Tool pair detection**: Finding and preserving tool_use/tool_result pairs
- **Protected tools**: Ensuring protected tools are never compressed
- **Message separation**: Logic for deciding what to preserve vs compress
- **Token estimation**: Accuracy of token counting
- **Error handling**: LLM failures, unknown strategies

### 3. Short-Term Memory Tests (`test_short_term.py`)
- **Basic operations**: add, get, clear, count
- **Capacity management**: FIFO eviction, is_full checks
- **Edge cases**: max_size=0, max_size=1, very large max_size
- **Sequential operations**: Mixed add/clear/check sequences

### 4. Integration Tests (`test_integration.py`)
- **Tool call/result integration**: The main focus for debugging the mismatch issue
  - Tool pairs survive compression cycles
  - Multiple compressions
  - Interleaved tool calls
  - Orphaned tool_use detection
  - Orphaned tool_result detection
- **Full conversation lifecycle**: Long conversations with multiple compressions
- **Mixed content**: Text and tool content together
- **Edge case scenarios**: Rapid compressions, alternating strategies

## Running Tests

### Run all memory tests
```bash
pytest test/memory/ -v
```

### Run specific test file
```bash
pytest test/memory/test_memory_manager.py -v
```

### Run specific test class
```bash
pytest test/memory/test_integration.py::TestToolCallResultIntegration -v
```

### Run specific test
```bash
pytest test/memory/test_memory_manager.py::TestToolCallMatching::test_tool_pairs_preserved_together -v
```

### Run with coverage
```bash
pytest test/memory/ --cov=memory --cov-report=html
```

### Run tests and show print output
```bash
pytest test/memory/ -v -s
```

## Key Test Fixtures

Defined in `conftest.py`:

- `mock_llm`: Mock LLM that doesn't make real API calls
- `simple_messages`: List of simple text messages
- `tool_use_messages`: Messages with tool_use and tool_result pairs
- `protected_tool_messages`: Messages with tool call pairs
- `mismatched_tool_messages`: Messages with mismatched tool pairs (for bug testing)

## Critical Tests for Tool Matching Issue

The user reported issues with tool_call and tool_result mismatches. The following tests specifically target this:

1. `test_tool_pairs_preserved_together` - Ensures tool pairs stay together
2. `test_mismatched_tool_calls_detected` - Documents current behavior with mismatches
3. `test_tool_pairs_survive_compression_cycle` - Integration test for compression
4. `test_orphaned_tool_use_detection` - Detects orphaned tool_use
5. `test_orphaned_tool_result_detection` - Detects orphaned tool_result
6. `test_tool_pair_preservation_rule` - Verifies pairs aren't split

## Test Execution Strategy

1. **Unit tests first**: Run individual component tests to isolate issues
2. **Integration tests**: Run full integration tests to catch interaction bugs
3. **Fix and iterate**: When tests fail, they pinpoint the exact issue
4. **Regression prevention**: Keep all tests passing to prevent regressions

## Expected Behavior

### Tool Pair Matching Rules

The memory system MUST follow these rules:

1. **Tool pairs stay together**: If `tool_use` is preserved, its `tool_result` must be preserved
2. **No split pairs**: Tool pairs cannot be split between preserved and compressed messages
3. **Protected tools never compressed**: Tools in PROTECTED_TOOLS are always preserved
4. **Orphan detection**: The system should not create orphaned tool_use or tool_result

### Compression Triggers

Compression is triggered when:
1. Short-term memory is full (`short_term_message_count` reached)
2. Current tokens exceed `target_working_memory_tokens` (soft limit)
3. Current tokens exceed `compression_threshold` (hard limit)

## Debugging Failed Tests

If tests fail:

1. **Read the assertion message**: It will show what was expected vs actual
2. **Check tool IDs**: Look for mismatched tool_use_ids vs tool_result_ids
3. **Enable print output**: Use `pytest -v -s` to see debug prints
4. **Run specific test**: Isolate the failing test to understand the issue
5. **Check recent changes**: Compare with known-good behavior

## Adding New Tests

When adding new tests:

1. **Use existing fixtures**: Reuse `mock_llm` and message fixtures
2. **Follow naming conventions**: `test_<what_is_being_tested>`
3. **Add docstrings**: Explain what the test verifies
4. **Group related tests**: Use test classes to organize related tests
5. **Test both success and failure**: Test expected behavior and error cases

## Notes

- Tests use a `MockLLM` to avoid making real API calls
- Token estimation in tests uses the same logic as the actual system
- Integration tests may take longer to run due to multiple operations
- Some tests document current behavior (e.g., mismatched pairs) for debugging
