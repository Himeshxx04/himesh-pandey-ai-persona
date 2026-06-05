"""
Diagnostic: hit ElevenLabs TTS directly with the .env credentials, bypassing
LiveKit. Prints the actual API error if any. Run from repo root:

    python voice/test_elevenlabs.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

print("=" * 60)
print(f"API key set?       {'YES' if API_KEY else 'NO'}  ({len(API_KEY)} chars, starts {API_KEY[:6]}...)")
print(f"Voice ID set?      {'YES' if VOICE_ID else 'NO'}  ({len(VOICE_ID)} chars: {VOICE_ID!r})")
print("=" * 60)

if not API_KEY or not VOICE_ID:
    print("FAIL: missing env vars")
    sys.exit(1)

import httpx

# ── Step 1: does the API key even work? List user's subscription info.
print("\n[1/4] Checking API key validity via /v1/user/subscription...")
r = httpx.get(
    "https://api.elevenlabs.io/v1/user/subscription",
    headers={"xi-api-key": API_KEY},
    timeout=15,
)
print(f"  HTTP {r.status_code}")
if r.status_code != 200:
    print(f"  RESPONSE: {r.text[:500]}")
    sys.exit(1)
sub = r.json()
print(f"  Tier: {sub.get('tier')}")
print(f"  Character quota: used {sub.get('character_count')}/{sub.get('character_limit')}")

# ── Step 2: does this voice ID exist and is it accessible to you?
print(f"\n[2/4] Checking voice {VOICE_ID!r} via /v1/voices/{VOICE_ID}...")
r = httpx.get(
    f"https://api.elevenlabs.io/v1/voices/{VOICE_ID}",
    headers={"xi-api-key": API_KEY},
    timeout=15,
)
print(f"  HTTP {r.status_code}")
if r.status_code != 200:
    print(f"  RESPONSE: {r.text[:500]}")
    print("\n  >>> Likely cause: voice ID is wrong, OR the voice is not added to your library.")
    print("  >>> Fix: in ElevenLabs UI, go to Voices > Voice Library, find your voice, click 'Add'.")
    sys.exit(1)
v = r.json()
print(f"  Voice name:     {v.get('name')}")
print(f"  Category:       {v.get('category')}   (premade/cloned/generated/professional)")
print(f"  Available?:     {v.get('available_for_tiers', 'n/a')}")

# ── Step 3: list models we have access to
print(f"\n[3/4] Listing models via /v1/models...")
r = httpx.get(
    "https://api.elevenlabs.io/v1/models",
    headers={"xi-api-key": API_KEY},
    timeout=15,
)
print(f"  HTTP {r.status_code}")
if r.status_code != 200:
    print(f"  RESPONSE: {r.text[:500]}")
    sys.exit(1)
models = r.json()
print(f"  Available models ({len(models)}):")
flash_found = False
for m in models:
    mid = m.get("model_id")
    name = m.get("name")
    can_use = m.get("can_use_style", True)  # rough proxy
    marker = "  <-- WE'RE USING" if mid == "eleven_flash_v2_5" else ""
    if mid == "eleven_flash_v2_5":
        flash_found = True
    print(f"    {mid:40s}  {name}{marker}")
if not flash_found:
    print("\n  >>> WARNING: eleven_flash_v2_5 is NOT in your accessible models.")
    print("  >>> Pick a different model from the list above.")

# ── Step 4: actually try TTS
print(f"\n[4/4] Synthesizing 'Hello, this is a test.' with eleven_flash_v2_5...")
r = httpx.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
    headers={
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
    },
    json={
        "text": "Hello, this is a test.",
        "model_id": "eleven_flash_v2_5",
    },
    timeout=30,
)
print(f"  HTTP {r.status_code}")
total = 0
if r.status_code == 200:
    for chunk in r.iter_bytes():
        total += len(chunk)
    print(f"  Audio bytes received: {total}")
    if total > 1000:
        print("  >>> SUCCESS: TTS works. Issue is in the LiveKit plugin config.")
    else:
        print("  >>> FAIL: 200 OK but ~no audio. Very unusual.")
else:
    print(f"  RESPONSE: {r.text[:1000]}")
    print("\n  >>> This is the actual error LiveKit was hitting. Diagnose from the message above.")
