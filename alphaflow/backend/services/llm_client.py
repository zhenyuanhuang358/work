"""Gemini LLM client using google-genai SDK."""
import json
import os
import re
from google import genai
from google.genai import types

from backend.prompts.analyst import (
    SYSTEM_PROMPT,
    EXTRACT_METRICS_PROMPT,
    TONE_ANALYSIS_PROMPT,
    MEMO_PROMPT,
)

_client: genai.Client | None = None
MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        _client = genai.Client(api_key=api_key)
    return _client


def _call(prompt: str, expect_json: bool = False) -> str:
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.2,
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    text = response.text.strip()
    if expect_json:
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


async def extract_metrics(data: dict) -> dict:
    prompt = EXTRACT_METRICS_PROMPT.replace("{data}", json.dumps(data, indent=2))
    text = _call(prompt, expect_json=True)
    return json.loads(text)


async def analyze_tone(content: str) -> dict:
    prompt = TONE_ANALYSIS_PROMPT.replace("{content}", content)
    text = _call(prompt, expect_json=True)
    return json.loads(text)


async def generate_memo(metrics: dict, tone: dict, context: dict) -> str:
    prompt = (
        MEMO_PROMPT
        .replace("{metrics}", json.dumps(metrics, indent=2))
        .replace("{tone}", json.dumps(tone, indent=2))
        .replace("{context}", json.dumps(context, indent=2))
    )
    return _call(prompt, expect_json=False)
