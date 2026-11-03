"""Targeted yes/no visual checks against a label image.

Used by the investigator's visual_check tool to ask a specific question derived from an
alert's known_differences. The model only answers yes/no with a confidence; it never judges
"does this look fake". No verdict is produced here.
"""

from __future__ import annotations

import base64
import json

import httpx

_QUESTION_PROMPT = (
    "Answer this yes/no question about the product label in the image. "
    "Return ONLY valid JSON of the form {\"answer\": \"yes\" or \"no\", "
    "\"confidence\": 0.0 to 1.0, \"note\": \"a short reason\"}. "
    "Do not judge authenticity; answer only the literal question.\n\n"
    "Question: {question}"
)


def ask_visual_question(settings, image_bytes: bytes, question: str, transport: httpx.BaseTransport | None = None) -> dict | None:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.meta_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _QUESTION_PROMPT.replace("{question}", question)},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {settings.meta_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=45, transport=transport) as client:
            resp = client.post(
                settings.meta_api_base_url.rstrip("/") + "/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return None

    if not isinstance(content, str):
        return None
    parsed = _parse_json(content)
    if not isinstance(parsed, dict):
        return None
    answer = str(parsed.get("answer", "")).strip().lower()
    if answer not in ("yes", "no"):
        return None
    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "question": question,
        "answer": answer,
        "confidence": max(0.0, min(1.0, confidence)),
        "note": str(parsed.get("note", ""))[:200],
    }


def _parse_json(content: str) -> dict | None:
    import re

    if not isinstance(content, str):
        return None
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None
