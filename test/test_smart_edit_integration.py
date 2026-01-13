"""Quick integration test for SmartEditTool with Agent."""
import tempfile
from pathlib import Path

from config import Config
from llm import create_llm
from agent.react_agent import ReActAgent
from tools.smart_edit import SmartEditTool
from tools.file_ops import FileReadTool, FileWriteTool

def test_smart_edit_in_agent():
    """Test that SmartEditTool works when used by an agent."""

    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('''def calculate(x, y):
    result = x + y
    return result
''')
        temp_path = f.name

    try:
        # Create minimal agent with just SmartEditTool
        llm = create_llm(
            provider=Config.LLM_PROVIDER,
            api_key=Config.get_api_key(),
            model=Config.get_default_model(),
            retry_config=Config.get_retry_config()
        )

        tools = [
            FileReadTool(),
            FileWriteTool(),
            SmartEditTool(),
        ]

        agent = ReActAgent(
            llm=llm,
            tools=tools,
            max_iterations=5
        )

        # Task: use smart_edit to add a comment
        task = f"""Use the smart_edit tool to add a comment '# computed sum' after 'result = x + y' in {temp_path}.

Use mode="diff_replace", old_code="result = x + y", new_code="result = x + y  # computed sum"."""

        print(f"Testing SmartEditTool integration...")
        print(f"Temp file: {temp_path}")
        print(f"Task: {task}")
        print("-" * 60)

        result = agent.run(task)

        print("-" * 60)
        print(f"Agent result: {result}")

        # Verify the edit was made
        content = Path(temp_path).read_text()
        print(f"\nFile content after edit:\n{content}")

        assert "# computed sum" in content, "Edit was not applied!"
        print("\n✅ Integration test PASSED!")

    finally:
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        Path(temp_path + '.bak').unlink(missing_ok=True)

if __name__ == "__main__":
    test_smart_edit_in_agent()
