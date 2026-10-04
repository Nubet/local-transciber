from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise ValueError("Segment start cannot be negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Segment end must be greater than start")
        if not self.text.strip():
            raise ValueError("Segment text cannot be empty")


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise ValueError("Cue start cannot be negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Cue end must be greater than start")
        if not self.text.strip():
            raise ValueError("Cue text cannot be empty")


@dataclass(frozen=True, slots=True)
class SubtitleDocument:
    cues: tuple[SubtitleCue, ...]

    def __post_init__(self) -> None:
        previous_end = 0.0
        for cue in self.cues:
            if cue.start_seconds < previous_end:
                raise ValueError("Subtitle cues cannot overlap or be out of order")
            previous_end = cue.end_seconds

    @classmethod
    def from_segments(cls, segments: Iterable[TranscriptionSegment]) -> SubtitleDocument:
        return cls(
            tuple(
                SubtitleCue(segment.start_seconds, segment.end_seconds, segment.text.strip())
                for segment in segments
            )
        )
