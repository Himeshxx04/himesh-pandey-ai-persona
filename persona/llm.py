"""
Provider-agnostic LLM wrapper.

Reads LLM_PROVIDER, LLM_MODEL, LLM_API_KEY from environment.
Supports: openai | anthropic | groq
All three expose the same OpenAI-compatible chat completion interface.
"""

import os
from typing import Iterator

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
