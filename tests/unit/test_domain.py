import pytest

from subtitle_app.domain import SubtitleCue, SubtitleDocument, TranscriptionSegment


def test_document_is_created_from_segments() -> None:
    document = SubtitleDocument.from_segments(
        (TranscriptionSegment(0.0, 1.25, "  Hello  "),)
    )

    assert document.cues == (SubtitleCue(0.0, 1.25, "Hello"),)


def test_overlapping_cues_are_rejected() -> None:
    with pytest.raises(ValueError, match="overlap"):
        SubtitleDocument((SubtitleCue(0.0, 2.0, "A"), SubtitleCue(1.0, 3.0, "B")))
