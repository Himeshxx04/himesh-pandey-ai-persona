"""List premade voices accessible to the current ElevenLabs API key."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

import httpx

api_key = os.getenv("ELEVENLABS_API_KEY", "")
if not api_key:
    print("ELEVENLABS_API_KEY missing in .env")
    sys.exit(1)

r = httpx.get(
    "https://api.elevenlabs.io/v1/voices",
    headers={"xi-api-key": api_key},
    timeout=15,
)
r.raise_for_status()
voices = r.json()["voices"]

print(f"{'VOICE_ID':30s}  {'NAME':25s}  {'GENDER':8s}  {'ACCENT':12s}  {'AGE':10s}  DESCRIPTION")
print("-" * 130)
for v in voices:
    if v.get("category") != "premade":
        continue
    labels = v.get("labels", {}) or {}
    print(
        f"{v['voice_id']:30s}  "
        f"{v['name']:25s}  "
        f"{labels.get('gender','?'):8s}  "
        f"{labels.get('accent','?'):12s}  "
        f"{labels.get('age','?'):10s}  "
        f"{labels.get('description','')}"
    )
