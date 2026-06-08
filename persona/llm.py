"""
Provider-agnostic LLM wrapper.

Reads LLM_PROVIDER, LLM_MODEL, LLM_API_KEY from environment.
Supports: openai | anthropic | groq
All three expose the same OpenAI-compatible chat completion interface.
"""

import json
import os
from typing import Any, Callable, Iterator

from dotenv import load_dotenv

load_dotenv()

_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
_API_KEY = os.getenv("LLM_API_KEY", "")

# Base URLs for OpenAI-compatible providers
_BASE_URLS = {
    "openai": None,  # default
    "groq": "https://api.groq.com/openai/v1",
}


def _get_client():
    """Lazy-initialise the right client."""
    if _PROVIDER == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=_API_KEY)
    else:
        import openai
        kwargs = {"api_key": _API_KEY}
        if _PROVIDER in _BASE_URLS and _BASE_URLS[_PROVIDER]:
            kwargs["base_url"] = _BASE_URLS[_PROVIDER]
        return openai.OpenAI(**kwargs)


def chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 800) -> str:
    """
    Single-turn chat completion. Returns the assistant's reply as a string.

    Args:
        messages: list of {"role": ..., "content": ...}
        temperature: 0.0–1.0; lower = more deterministic / grounded
        max_tokens: cap on output length

    Returns:
        assistant reply string
    """
    client = _get_client()

    if _PROVIDER == "anthropic":
        # Anthropic separates system messages
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=user_messages,
        )
        return resp.content[0].text
    else:
        # OpenAI-compatible (openai, groq)
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content


def stream(messages: list[dict], temperature: float = 0.3, max_tokens: int = 800) -> Iterator[str]:
    """
    Streaming variant — yields text chunks as they arrive.
    Used by the voice agent for lowest-latency first-token delivery.
    """
    client = _get_client()

    if _PROVIDER == "anthropic":
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        with client.messages.stream(
            model=_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=user_messages,
        ) as s:
            for text in s.text_stream:
                yield text
    else:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Tool-using chat (function calling) ─────────────────────────────────────

def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    tool_handlers: dict[str, Callable[[dict], Any]],
    temperature: float = 0.3,
    max_tokens: int = 800,
    max_rounds: int = 4,
    force_first_tool: str | None = None,
) -> tuple[str, list[str]]:
    """
    Run a chat completion that may invoke tools. Handles the full
    LLM→tool→LLM loop until the model returns a final text answer.

    Returns (final_text, tool_names_called).

    `tools`         — OpenAI-format tool schemas (list of {type, function}).
    `tool_handlers` — { tool_name: callable(args_dict) -> json-serializable result }.
    `force_first_tool` — if set, the FIRST round forces tool_choice to this
                         specific function name. Subsequent rounds use "auto".
                         Use to break gpt-4o-mini's indecision on multi-turn
                         flows (e.g. force book_slot when user has provided
                         slot+name+email but the model keeps second-guessing).

    Only supported for OpenAI-compatible providers (OpenAI, Groq).
    Anthropic uses a different tool-calling shape; if you switch to it,
    re-implement this for the messages.tool_use format.
    """
    if _PROVIDER == "anthropic":
        # Fallback: Anthropic tool-use lives in a different API shape.
        # For now, no tools — just call chat() and skip tooling.
        return chat(messages, temperature=temperature, max_tokens=max_tokens), []

    client = _get_client()
    called: list[str] = []

    # Work on a local copy so we don't mutate the caller's history
    convo = list(messages)

    for _round in range(max_rounds):
        # Force a specific tool ONLY on the first round, if requested.
        # After the tool runs, we want the model free to format the result.
        if _round == 0 and force_first_tool:
            tool_choice: Any = {
                "type": "function",
                "function": {"name": force_first_tool},
            }
        else:
            tool_choice = "auto"

        resp = client.chat.completions.create(
            model=_MODEL,
            messages=convo,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        msg = resp.choices[0].message

        # If the model called one or more tools, execute them and continue
        if msg.tool_calls:
            # Append the assistant's tool-call message itself to the convo
            convo.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            # Execute each tool and append its result
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                called.append(tool_name)

                handler = tool_handlers.get(tool_name)
                if handler is None:
                    result: Any = {"error": f"unknown tool: {tool_name}"}
                else:
                    try:
                        result = handler(args)
                    except Exception as e:
                        result = {"error": str(e)}

                convo.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
            # Loop again — let the model see the tool results and produce
            # a final response (or call more tools).
            continue

        # No tool call — model returned final text
        return (msg.content or "").strip(), called

    # Exceeded max rounds — return whatever the last message had
    return "I'm having trouble completing that — let me know if you'd like to try again.", called
