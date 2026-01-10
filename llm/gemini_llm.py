"""Google Gemini LLM implementation using the new google.genai SDK."""
from typing import List, Dict, Any, Optional
import json

from .base import BaseLLM, LLMMessage, LLMResponse, ToolCall, ToolResult
from .retry import with_retry, RetryConfig
from utils import get_logger

logger = get_logger(__name__)


class GeminiLLM(BaseLLM):
    """Google Gemini LLM provider using google.genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro", **kwargs):
        """Initialize Gemini LLM.

        Args:
            api_key: Google AI API key
            model: Gemini model identifier (e.g., gemini-2.5-pro, gemini-1.5-flash)
            **kwargs: Additional configuration (including retry_config, base_url)
        """
        super().__init__(api_key, model, **kwargs)

        # Configure retry behavior
        self.retry_config = kwargs.get('retry_config', RetryConfig(
            max_retries=5,
            initial_delay=2.0,
            max_delay=60.0
        ))

        try:
            from google import genai
            from google.genai import types

            # Get base_url from kwargs, or use None (default)
            base_url = kwargs.get('base_url', None)

            # Initialize client with optional base_url
            if base_url:
                self.client = genai.Client(
                    api_key=api_key,
                    http_options={'api_endpoint': base_url}
                )
            else:
                self.client = genai.Client(api_key=api_key)

            self.types = types
            self.model_name = model
        except ImportError:
            raise ImportError(
                "Google GenAI package not installed. "
                "Install with: pip install google-genai"
            )

    @with_retry()
    def _make_api_call(self, model_name, messages, tools, config):
        """Internal method to make API call with retry logic."""
        if tools:
            return self.client.models.generate_content(
                model=model_name,
                contents=messages,
                config=config
            )
        else:
            return self.client.models.generate_content(
                model=model_name,
                contents=messages,
                config=config
            )

    def call(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """Call Gemini API with automatic retry on rate limits.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool schemas
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            LLMResponse with unified format
        """
        # Convert messages to Gemini format
        gemini_messages = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                # Check if this is a function response (structured content)
                if isinstance(msg.content, list) and msg.content and isinstance(msg.content[0], dict):
                    # Check if it's function responses
                    if msg.content[0].get("type") == "function_response":
                        # Convert to Gemini function_response parts
                        parts = []
                        for func_resp in msg.content:
                            parts.append({
                                "function_response": {
                                    "name": func_resp["name"],
                                    "response": func_resp["response"]
                                }
                            })
                        gemini_messages.append({
                            "role": "user",
                            "parts": parts
                        })
                    else:
                        # Regular text message
                        gemini_messages.append({
                            "role": "user",
                            "parts": [{"text": str(msg.content)}]
                        })
                else:
                    # Regular text message
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": str(msg.content)}]
                    })
            elif msg.role == "assistant":
                # Handle assistant messages
                if isinstance(msg.content, str):
                    gemini_messages.append({
                        "role": "model",
                        "parts": [{"text": msg.content}]
                    })
                else:
                    # Handle raw Gemini response or content blocks
                    parts = []

                    # Check if this is a raw Gemini response object
                    if hasattr(msg.content, "candidates"):
                        # Extract parts from the raw response
                        try:
                            for candidate in msg.content.candidates:
                                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                                    for part in candidate.content.parts:
                                        # Handle text parts
                                        if hasattr(part, "text") and part.text:
                                            parts.append({"text": part.text})
                                        # Handle function_call parts
                                        elif hasattr(part, "function_call"):
                                            fc = part.function_call
                                            # Convert args to regular dict
                                            args_dict = {}
                                            if hasattr(fc, "args"):
                                                for key, value in fc.args.items():
                                                    args_dict[key] = value
                                            parts.append({
                                                "function_call": {
                                                    "name": fc.name,
                                                    "args": args_dict
                                                }
                                            })
                        except (ValueError, AttributeError) as e:
                            pass
                    else:
                        # Handle content blocks (list format)
                        for block in msg.content:
                            try:
                                if hasattr(block, "text") and block.text:
                                    parts.append({"text": block.text})
                            except (ValueError, AttributeError):
                                pass

                    if parts:
                        gemini_messages.append({
                            "role": "model",
                            "parts": parts
                        })

        # Convert tools to new SDK format if provided
        tool_config = None
        if tools:
            # Create function declarations using new SDK types
            function_declarations = []
            for tool in tools:
                function_declarations.append(
                    self.types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool["description"],
                        parameters=tool["input_schema"]
                    )
                )

            # Create tools list with function calling config
            tool_config = self.types.Tool(
                function_declarations=function_declarations
            )

        # Prepare generation config using new SDK types
        config_dict = {
            "max_output_tokens": max_tokens,
            "system_instruction": system_instruction if system_instruction else None,
        }

        # Add tools if provided
        if tool_config:
            config_dict["tools"] = [tool_config]
            # Enable automatic function calling
            config_dict["tool_config"] = self.types.ToolConfig(
                function_calling_config=self.types.FunctionCallingConfig(
                    mode='AUTO'
                )
            )

        config_dict.update(kwargs)
        config = self.types.GenerateContentConfig(**config_dict)

        # Make API call with retry logic
        try:
            response = self._make_api_call(
                self.model_name,
                gemini_messages,
                tool_config,
                config
            )

            # Log token usage
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                logger.debug(f"Token Usage: Input={usage.prompt_token_count}, Output={usage.candidates_token_count}, Total={usage.total_token_count}")

            # Determine stop reason
            if hasattr(response, "candidates") and response.candidates:
                finish_reason = response.candidates[0].finish_reason
                # Check for function calls
                has_function_call = False
                try:
                    if hasattr(response.candidates[0], "content") and hasattr(response.candidates[0].content, "parts"):
                        has_function_call = any(
                            hasattr(part, "function_call") and part.function_call
                            for part in response.candidates[0].content.parts
                        )
                except (ValueError, AttributeError):
                    pass

                if has_function_call:
                    stop_reason = "tool_use"
                elif str(finish_reason) == "STOP":
                    stop_reason = "end_turn"
                elif str(finish_reason) == "MAX_TOKENS":
                    stop_reason = "max_tokens"
                else:
                    stop_reason = "end_turn"
            else:
                stop_reason = "end_turn"

            # Extract token usage
            usage_dict = None
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                usage_dict = {
                    "input_tokens": usage.prompt_token_count,
                    "output_tokens": usage.candidates_token_count
                }

            return LLMResponse(
                content=response,
                stop_reason=stop_reason,
                raw_response=response,
                usage=usage_dict
            )

        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {str(e)}")

    def extract_text(self, response: LLMResponse) -> str:
        """Extract text from Gemini response.

        Args:
            response: LLMResponse object

        Returns:
            Extracted text
        """
        try:
            return response.content.text
        except:
            return ""

    def extract_tool_calls(self, response: LLMResponse) -> List[ToolCall]:
        """Extract tool calls from Gemini response.

        Args:
            response: LLMResponse object

        Returns:
            List of ToolCall objects
        """
        tool_calls = []

        try:
            if hasattr(response.content, "candidates"):
                for candidate in response.content.candidates:
                    if hasattr(candidate.content, "parts"):
                        for part in candidate.content.parts:
                            if hasattr(part, "function_call"):
                                fc = part.function_call
                                # Convert arguments to dict
                                args = {}
                                if hasattr(fc, "args"):
                                    for key, value in fc.args.items():
                                        args[key] = value

                                tool_calls.append(ToolCall(
                                    id=f"call_{fc.name}",  # Gemini doesn't provide IDs
                                    name=fc.name,
                                    arguments=args
                                ))
        except:
            pass

        return tool_calls

    def format_tool_results(self, results: List[ToolResult]) -> LLMMessage:
        """Format tool results for Gemini.

        Args:
            results: List of tool results

        Returns:
            LLMMessage with formatted results as structured function responses
        """
        # Gemini expects function_response parts
        # Return structured content that will be converted properly
        function_responses = []
        for result in results:
            # Extract function name from tool_call_id (format: "call_function_name")
            function_name = result.tool_call_id.replace("call_", "", 1)

            function_responses.append({
                "type": "function_response",
                "name": function_name,
                "response": {"result": result.content}
            })

        return LLMMessage(role="user", content=function_responses)

    @property
    def supports_tools(self) -> bool:
        """Gemini supports function calling."""
        return True
