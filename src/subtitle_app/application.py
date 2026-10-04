from collections.abc import Callable, Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from .domain import SubtitleDocument, TranscriptionSegment


class AudioExtractor(Protocol):
    def extract(self, video_path: Path, audio_path: Path) -> None: ...


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        progress: Callable[[float], None] | None = None,
    ) -> Iterable[TranscriptionSegment]: ...


class VttWriter(Protocol):
    def write(self, document: SubtitleDocument, output_path: Path) -> None: ...


class ProgressReporter(Protocol):
    def report(self, value: float, message: str) -> None: ...


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...


class TranscriptionCancelled(Exception):
    """Raised when a running transcription is cancelled by the user."""


class TranscribeVideo:
    def __init__(
        self,
        audio_extractor: AudioExtractor,
        transcriber: Transcriber,
        vtt_writer: VttWriter,
    ):
        self._audio_extractor = audio_extractor
        self._transcriber = transcriber
        self._vtt_writer = vtt_writer

    def execute(
        self,
        video_path: Path,
        output_path: Path,
        language: str | None = None,
        reporter: ProgressReporter | None = None,
        cancellation: CancellationToken | None = None,
    ) -> SubtitleDocument:
        if not video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        report = reporter.report if reporter else lambda _value, _message: None
        if cancellation and cancellation.is_cancelled():
            raise TranscriptionCancelled

        with TemporaryDirectory(prefix="subtitle-") as temporary_directory:
            audio_path = Path(temporary_directory) / "audio.wav"
            report(0.05, "Extracting audio")
            self._audio_extractor.extract(video_path, audio_path)
            if cancellation and cancellation.is_cancelled():
                raise TranscriptionCancelled

            report(0.20, "Transcribing audio")
            segments = []
            for segment in self._transcriber.transcribe(
                audio_path,
                language=language,
                progress=lambda value: report(0.20 + value * 0.70, "Transcribing audio"),
            ):
                if cancellation and cancellation.is_cancelled():
                    raise TranscriptionCancelled
                segments.append(segment)
            document = SubtitleDocument.from_segments(segments)

        if cancellation and cancellation.is_cancelled():
            raise TranscriptionCancelled
        report(0.95, "Writing subtitles")
        self._vtt_writer.write(document, output_path)
        report(1.0, "Completed")
        return document
