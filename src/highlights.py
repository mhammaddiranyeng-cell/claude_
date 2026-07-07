"""Pick clip-worthy windows out of a transcript.

Heuristic scoring only (no external API calls): trigger-phrase hits,
speech density (words/sec, favors energetic back-and-forth over dead air),
and even spacing across the source so picks aren't clustered in one spot.
Swap in an LLM-based scorer later if you want smarter picks.
"""
from dataclasses import dataclass
from typing import List

from .transcribe import Segment


@dataclass
class Highlight:
    start: float
    end: float
    text: str
    score: float


def _score_window(segments: List[Segment], trigger_phrases: List[str]) -> float:
    text = " ".join(s.text for s in segments).lower()
    word_count = sum(len(s.text.split()) for s in segments)
    duration = max(segments[-1].end - segments[0].start, 1e-6)

    trigger_hits = sum(text.count(p.lower()) for p in trigger_phrases)
    density = word_count / duration  # words per second

    return trigger_hits * 5.0 + density


def find_highlights(
    segments: List[Segment],
    trigger_phrases: List[str],
    min_clip_seconds: float = 20,
    max_clip_seconds: float = 90,
    max_clips: int = 8,
) -> List[Highlight]:
    if not segments:
        return []

    candidates: List[Highlight] = []
    n = len(segments)
    for i in range(n):
        window = [segments[i]]
        for j in range(i + 1, n):
            duration = segments[j].end - segments[i].start
            if duration > max_clip_seconds:
                break
            window.append(segments[j])
            if duration >= min_clip_seconds:
                score = _score_window(window, trigger_phrases)
                candidates.append(
                    Highlight(
                        start=segments[i].start,
                        end=segments[j].end,
                        text=" ".join(s.text for s in window),
                        score=score,
                    )
                )

    candidates.sort(key=lambda h: h.score, reverse=True)

    picked: List[Highlight] = []
    for c in candidates:
        if any(not (c.end <= p.start or c.start >= p.end) for p in picked):
            continue  # overlaps an already-picked clip
        picked.append(c)
        if len(picked) >= max_clips:
            break

    picked.sort(key=lambda h: h.start)
    return picked
