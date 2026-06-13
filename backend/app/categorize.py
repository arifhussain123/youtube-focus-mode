"""Video categorization via the Claude API (Anthropic Python SDK).

One batched, low-cost classification call per group of uncategorized videos:
all titles go into a single request and Claude returns a JSON array mapping
each video_id to one fixed-taxonomy category. Uses Haiku 4.5 — cheapest model,
well-suited to short-title classification.
"""

import json
import os

import anthropic

# claude-haiku-4-5: fastest / cheapest, ideal for high-volume title classification.
MODEL = "claude-haiku-4-5"

# Fixed taxonomy. Claude must pick exactly one of these per video; anything it
# returns outside the list is coerced to "Other".
CATEGORIES = [
    "Education",
    "Tech & Programming",
    "Entertainment",
    "Music",
    "Gaming",
    "News & Politics",
    "Sports",
    "Science",
    "Business & Finance",
    "Health & Fitness",
    "Food & Cooking",
    "Lifestyle & Vlogs",
    "Other",
]
_VALID = set(CATEGORIES)

_client = None


def is_configured() -> bool:
    """True if an API key is available; the endpoint degrades gracefully if not."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # Reads ANTHROPIC_API_KEY from the environment automatically.
        _client = anthropic.Anthropic()
    return _client


def _parse_json_array(text: str):
    """Extract the JSON array from the model's response, tolerating stray prose."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []


def categorize_videos(videos: list[dict]) -> dict[str, str]:
    """Classify a batch of videos.

    `videos` is a list of {"video_id", "title", "channel"}.
    Returns {video_id: category}. Returns {} if nothing to do.
    """
    if not videos:
        return {}

    listing = "\n".join(
        f'- video_id: {v["video_id"]} | title: {v.get("title") or "(untitled)"}'
        f' | channel: {v.get("channel") or "(unknown)"}'
        for v in videos
    )
    system = (
        "You classify YouTube videos into exactly one topic category from a "
        "fixed list, using the title and channel. Respond with ONLY a JSON "
        "array — no prose, no code fences."
    )
    user = (
        f"Allowed categories: {', '.join(CATEGORIES)}\n\n"
        "For each video below, choose the single best-fitting category from the "
        "allowed list (use \"Other\" if none fit). Return a JSON array of objects, "
        'each with keys "video_id" and "category". The category must match one of '
        "the allowed categories exactly.\n\n"
        f"Videos:\n{listing}"
    )

    # Small JSON output; scale a little with batch size. No thinking/effort —
    # this is a quick classification, and effort would error on Haiku.
    max_tokens = min(4096, 256 + len(videos) * 48)
    message = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    text = "".join(block.text for block in message.content if block.type == "text")
    result: dict[str, str] = {}
    for item in _parse_json_array(text):
        vid = item.get("video_id")
        cat = item.get("category")
        if vid:
            result[vid] = cat if cat in _VALID else "Other"
    return result
