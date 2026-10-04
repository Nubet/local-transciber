from pathlib import Path

import pytest

from subtitle_app.application import TranscribeVideo, TranscriptionCancelled
from subtitle_app.domain import TranscriptionSegment


class FakeExtractor:
    def extract(self, video_path: Path, audio_path: Path) -> None:
        audio_path.write_bytes(b"audio")


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language=None, progress=None):
        return [TranscriptionSegment(0.0, 1.0, "Hello")]


class FakeWriter:
    def write(self, document, output_path: Path) -> None:
        output_path.write_text(document.cues[0].text, encoding="utf-8")


class CancelledToken:
    def is_cancelled(self) -> bool:
        return True


def test_transcribe_video_orchestrates_pipeline(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    output = tmp_path / "subtitles.vtt"
    video.write_bytes(b"video")

    document = TranscribeVideo(FakeExtractor(), FakeTranscriber(), FakeWriter()).execute(
        video, output, language="pl"
    )

    assert document.cues[0].text == "Hello"
    assert output.read_text(encoding="utf-8") == "Hello"


def test_transcribe_video_can_be_cancelled_before_start(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    with pytest.raises(TranscriptionCancelled):
        TranscribeVideo(FakeExtractor(), FakeTranscriber(), FakeWriter()).execute(
            video,
            tmp_path / "subtitles.vtt",
            cancellation=CancelledToken(),
        )
