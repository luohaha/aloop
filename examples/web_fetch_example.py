"""Example usage of WebFetchTool with ReAct Agent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from agent.react_agent import ReActAgent
from llm import create_llm
from tools.web_fetch import WebFetchTool


def main():
    """Run WebFetchTool examples."""
    print("=" * 60)
    print("WebFetchTool Example")
    print("=" * 60)

    try:
        Config.validate()
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Please set your API key in the .env file")
        return

    llm = create_llm(
        provider=Config.LLM_PROVIDER,
        api_key=Config.get_api_key(),
        model=Config.get_default_model(),
        retry_config=Config.get_retry_config(),
        base_url=Config.get_base_url(),
    )

    agent = ReActAgent(
        llm=llm,
        tools=[WebFetchTool()],
        max_iterations=8,
    )

    print("\n--- Example 1: Fetch web page (raw tool output) ---")
    result1 = agent.run(
        "Use the web_fetch tool to fetch https://github.com/luohaha/agentic-loop in markdown format with a 20s timeout. "
        "Return the raw tool output JSON without extra commentary."
    )
    print(f"\nResult:\n{result1}")

    print("\n--- Example 2: Invalid URL error ---")
    result2 = agent.run(
        "Call web_fetch with url 'example.com' and return the raw tool output JSON only."
    )
    print(f"\nResult:\n{result2}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
