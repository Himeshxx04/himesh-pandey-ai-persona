"""
Render build step: decode base64-encoded corpus files from env vars.

Why: resume.pdf and about_me.md are gitignored (personal data).
On Render we store them as base64 env vars (RESUME_B64, ABOUT_ME_B64)
and decode them at build time so the FAISS indexer can read them.

Usage (called automatically by render.yaml buildCommand):
    python scripts/decode_corpus.py
"""

import base64
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def decode_var(env_var: str, dest: Path, label: str) -> bool:
    val = os.getenv(env_var, "").strip()
    if not val:
        print(f"[decode_corpus] WARNING: {env_var} not set — {label} will be missing from corpus.")
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(val))
        print(f"[decode_corpus] Decoded {env_var} -> {dest} ({dest.stat().st_size} bytes)")
        return True
    except Exception as e:
        print(f"[decode_corpus] ERROR decoding {env_var}: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    ok1 = decode_var("RESUME_B64",   REPO_ROOT / "corpus" / "resume.pdf",   "resume")
    ok2 = decode_var("ABOUT_ME_B64", REPO_ROOT / "corpus" / "about_me.md",  "about_me")
    if not ok1 and not ok2:
        print("[decode_corpus] No corpus files decoded. Indexer will only use GitHub content.")
    sys.exit(0)  # never fail the build — GitHub content alone is better than nothing
