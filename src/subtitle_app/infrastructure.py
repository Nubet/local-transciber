import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from .domain import SubtitleDocument, TranscriptionSegment


class FfmpegAudioExtractor:
    def __init__(self, executable: str = "ffmpeg") -> None:
        self._executable = executable

    def extract(self, video_path: Path, audio_path: Path) -> None:
        command = [
            self._executable, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
            "-f", "wav", str(audio_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("FFmpeg is not installed or not available on PATH") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or "unknown FFmpeg error"
            raise RuntimeError(f"Audio extraction failed: {detail}") from error


def _format_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02}.{milliseconds:03}"


class WebVttWriter:
    def write(self, document: SubtitleDocument, output_path: Path) -> None:
        lines = ["WEBVTT", ""]
        for cue in document.cues:
            timing = f"{_format_timestamp(cue.start_seconds)} --> "
            timing += _format_timestamp(cue.end_seconds)
            lines.extend([timing, cue.text, ""])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")


class FasterWhisperTranscriber:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        try:
            from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]
        except ImportError as error:
            raise RuntimeError(
                "faster-whisper is required. Install it with: uv sync --extra transcription"
            ) from error
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        progress: Callable[[float], None] | None = None,
    ) -> Iterable[TranscriptionSegment]:
        audio = _decode_audio_with_ffmpeg(audio_path)
        segments, info = self._model.transcribe(
            audio, language=language, vad_filter=True,
        )
        duration = max(info.duration, 1.0)
        for segment in segments:
            yield TranscriptionSegment(segment.start, segment.end, segment.text)
            if progress:
                progress(min(segment.end / duration, 0.99))
        if progress:
            progress(1.0)


def _decode_audio_with_ffmpeg(audio_path: Path):
    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError("numpy is required for audio decoding") from error

    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as error:
        raise RuntimeError("FFmpeg is not installed or not available on PATH") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip() or "unknown FFmpeg error"
        raise RuntimeError(f"Audio decoding failed: {detail}") from error

    samples = np.frombuffer(result.stdout, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0
