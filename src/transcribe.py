"""Transcribe a source video to word-level timestamps using faster-whisper."""
from dataclasses import dataclass
from typing import List

from faster_whisper import WhisperModel


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: List[Word]


def transcribe(video_path: str, model_size: str = "small", device: str = "auto") -> List[Segment]:
    model = WhisperModel(model_size, device=device, compute_type="int8")
    segments, _info = model.transcribe(video_path, word_timestamps=True, vad_filter=True)

    result = []
    for seg in segments:
        words = [Word(w.start, w.end, w.word.strip()) for w in (seg.words or [])]
        result.append(Segment(start=seg.start, end=seg.end, text=seg.text.strip(), words=words))
    return result
