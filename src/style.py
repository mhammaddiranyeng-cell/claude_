"""Pick editing knobs (cuts, zoom, caption style) from a campaign's brief.

Rule-based keyword matching -- deterministic and needs no API key. Swap
choose_style() for an LLM call later if you want subtler judgment; the
EditingStyle shape is what pipeline.py consumes either way.
"""
from dataclasses import dataclass

_HIGH_ENERGY_WORDS = [
    "energetic", "high energy", "hype", "fast-paced", "fast paced",
    "gaming", "reaction", "funny", "comedy", "meme",
]
_CALM_WORDS = [
    "calm", "educational", "podcast", "interview", "documentary",
    "informative", "relaxed", "soothing", "explainer",
]


@dataclass
class EditingStyle:
    jump_cuts: bool = True
    kenburns: bool = False
    caption_style: str = "karaoke"  # "karaoke" | "line"
    silence_min_duration: float = 0.4


def choose_style(description: str) -> EditingStyle:
    text = (description or "").lower()
    style = EditingStyle()

    if any(w in text for w in _CALM_WORDS):
        style.kenburns = True
        style.caption_style = "line"
        style.silence_min_duration = 0.6  # only cut longer pauses, keep a natural pace

    if any(w in text for w in _HIGH_ENERGY_WORDS):
        style.kenburns = True
        style.caption_style = "karaoke"
        style.silence_min_duration = 0.25  # cut aggressively, snappy pacing

    return style


def resolve_editing_config(editing_cfg: dict, description: str) -> EditingStyle:
    """Merge config.yaml's editing section with the auto-derived style.

    Each key in editing_cfg may be an explicit value or the string "auto",
    in which case the description-derived choice is used.
    """
    auto = choose_style(description)
    editing_cfg = editing_cfg or {}

    def pick(key: str, default):
        value = editing_cfg.get(key, "auto")
        return default if value == "auto" else value

    return EditingStyle(
        jump_cuts=pick("jump_cuts", auto.jump_cuts),
        kenburns=pick("kenburns", auto.kenburns),
        caption_style=pick("caption_style", auto.caption_style),
        silence_min_duration=pick("silence_min_duration", auto.silence_min_duration),
    )
