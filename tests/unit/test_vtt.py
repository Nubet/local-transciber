from pathlib import Path

from subtitle_app.domain import SubtitleCue, SubtitleDocument
from subtitle_app.infrastructure import WebVttWriter


def test_writer_creates_webvtt_file(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "subtitles.vtt"
    document = SubtitleDocument((SubtitleCue(1.2, 4.8, "Hello\nworld"),))

    WebVttWriter().write(document, output)

    assert output.read_text(encoding="utf-8") == (
        "WEBVTT\n\n00:00:01.200 --> 00:00:04.800\nHello\nworld\n"
    )
