import argparse
from pathlib import Path

from .application import ProgressReporter, TranscribeVideo
from .infrastructure import FasterWhisperTranscriber, FfmpegAudioExtractor, WebVttWriter


class ConsoleProgressReporter(ProgressReporter):
    def report(self, value: float, message: str) -> None:
        print(f"[{value:>6.1%}] {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe video into WebVTT subtitles")
    parser.add_argument("video", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-l", "--language")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()

    TranscribeVideo(
        FfmpegAudioExtractor(),
        FasterWhisperTranscriber(args.model, args.device, args.compute_type),
        WebVttWriter(),
    ).execute(args.video, args.output, args.language, ConsoleProgressReporter())


if __name__ == "__main__":
    main()
