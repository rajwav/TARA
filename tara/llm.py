import json
import logging
import requests
from typing import Optional, Any, Generator
from tara.config import config
from tara.tools import registry

logger = logging.getLogger("tara.llm")


class LLMClient:
    """Unified LLM interface supporting Groq (primary) and Ollama (local fallback) with streaming & tool execution."""

    def __init__(self):
        self.groq_client = None
        if config.groq_api_key and config.groq_api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=config.groq_api_key)
                logger.info(f"Groq client initialized with model {config.groq_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

    def generate(self, messages: list[dict[str, Any]], tools: Optional[list[dict[str, Any]]] = None) -> str:
        """Generate a complete text response."""
        chunks = list(self.generate_stream(messages, tools))
        return "".join(chunks)

    def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream text response tokens with tool execution support."""
        if config.default_provider == "groq" and self.groq_client:
            try:
                yielded = False
                for token in self._stream_groq(messages, tools):
                    yielded = True
                    yield token
                if yielded:
                    return
            except Exception as e:
                logger.warning(f"Groq streaming failed: {e}. Falling back to Ollama.")

        # Fallback to local Ollama
        try:
            for token in self._stream_ollama(messages, tools):
                yield token
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield "I am unable to reach any active reasoning engine (Groq or local Ollama). Please check your connection or start Ollama."

    def _stream_groq(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat completion from Groq, resolving any tool calls before streaming final output."""
        if not self.groq_client:
            return

        chat_history = [dict(m) for m in messages]
        candidate_models = [config.groq_model, "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]
        candidate_models = list(dict.fromkeys(candidate_models))

        for model in candidate_models:
            try:
                # Step 1: Tool execution loop (non-streaming)
                if tools:
                    for _ in range(3):
                        resp = self.groq_client.chat.completions.create(
                            model=model,
                            messages=chat_history,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.7,
                            max_tokens=1024
                        )
                        choice = resp.choices[0]
                        if choice.message.tool_calls:
                            assistant_entry = {
                                "role": "assistant",
                                "content": choice.message.content or "",
                                "tool_calls": [
                                    {
                                        "id": tc.id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.function.name,
                                            "arguments": tc.function.arguments
                                        }
                                    }
                                    for tc in choice.message.tool_calls
                                ]
                            }
                            chat_history.append(assistant_entry)
                            for tc in choice.message.tool_calls:
                                fn_name = tc.function.name
                                try:
                                    fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                                except Exception:
                                    fn_args = {}
                                tool_res = registry.execute(fn_name, fn_args)
                                chat_history.append({
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": tool_res
                                })
                        else:
                            if choice.message.content:
                                yield choice.message.content
                                return
                            break

                # Step 2: Stream final response tokens if no tools were called
                stream_resp = self.groq_client.chat.completions.create(
                    model=model,
                    messages=chat_history,
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )
                for chunk in stream_resp:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return

            except Exception as e:
                err_str = str(e)
                if "model_not_found" in err_str or "does not exist" in err_str or "decommissioned" in err_str:
                    logger.debug(f"Groq model '{model}' unavailable, trying next candidate.")
                    continue
                logger.warning(f"Groq streaming failed on model '{model}': {e}")
                raise

    def _stream_ollama(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat completion from local Ollama server."""
        url = f"{config.ollama_host}/api/chat"
        chat_history = [dict(m) for m in messages]

        # Step 1: Tool execution loop if tools provided
        if tools:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "parameters": t["function"]["parameters"]
                    }
                }
                for t in tools
            ]
            for _ in range(3):
                payload = {
                    "model": config.ollama_model,
                    "messages": chat_history,
                    "stream": False,
                    "tools": ollama_tools,
                    "options": {"temperature": 0.7}
                }
                try:
                    resp = requests.post(url, json=payload, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data.get("message", {})
                        tool_calls = msg.get("tool_calls", [])
                        if tool_calls:
                            chat_history.append(msg)
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                fn_name = fn.get("name", "")
                                fn_args = fn.get("arguments", {})
                                tool_res = registry.execute(fn_name, fn_args)
                                chat_history.append({"role": "tool", "content": tool_res})
                        else:
                            if msg.get("content") and len(chat_history) > len(messages):
                                yield msg.get("content")
                                return
                            break
                except Exception:
                    break

        # Step 2: Stream final response
        payload = {
            "model": config.ollama_model,
            "messages": chat_history,
            "stream": True,
            "options": {"temperature": 0.7}
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=30) as resp:
                if resp.status_code == 200:
                    for line in resp.iter_lines():
                        if line:
                            data = json.loads(line.decode("utf-8"))
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                else:
                    yield f"Error from Ollama: HTTP {resp.status_code}"
        except Exception as e:
            logger.error(f"Ollama streaming connection error: {e}")
            raise
