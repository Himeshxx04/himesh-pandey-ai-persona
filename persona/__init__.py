"""
persona package.

`Brain` is lazily imported via __getattr__ so that simply touching the
persona package (e.g. `from persona.tools.booking import BookingTool`)
does NOT pull in the heavy RAG stack (sentence-transformers, sklearn,
scipy, FAISS, langchain).

The voice agent's inference subprocess spawns a fresh Python interpreter
that imports voice/agent.py. Without this lazy export, that subprocess
would pay ~400MB to load Brain it never uses — which on Python 3.14
hits MemoryError during scipy import.

Usage stays the same:
    from persona import Brain           # works, loads on first access
    from persona.tools.booking import BookingTool   # cheap, no Brain load
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Hint for IDEs / type checkers without triggering import at runtime.
    from .brain import Brain  # noqa: F401


def __getattr__(name: str):
    if name == "Brain":
        from .brain import Brain  # heavy import deferred to first access
        return Brain
    raise AttributeError(f"module 'persona' has no attribute {name!r}")


__all__ = ["Brain"]
