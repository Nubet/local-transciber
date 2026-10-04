import asyncio
import sys
from pathlib import Path
from queue import Empty, Queue
from threading import Event

from .application import TranscriptionCancelled
from .domain import SubtitleCue, SubtitleDocument

UI_DIRECTORY = Path(__file__).parents[2] / "ui"
sys.path.insert(0, str(UI_DIRECTORY))

import slint  # noqa: E402


class App(slint.loader.app_window.AppWindow):
    def __init__(self) -> None:
        super().__init__()
        self._video_path: Path | None = None
        self._output_path: Path | None = None
        self._document: SubtitleDocument | None = None
        self._segment_model: slint.ListModel | None = None
        self._progress: Queue[tuple[float, str]] = Queue()
        self._cancel_event = Event()
        self._transcription_running = False

    @slint.callback()
    def choose_file(self) -> None:
        try:
            from tkinter import Tk, filedialog

            root = Tk()
            root.withdraw()
            selected = filedialog.askopenfilename(
                title="Choose video",
                filetypes=[
                    ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
        except Exception as error:
            self.status = f"Could not open file picker: {error}"
            self.status_kind = "error"
            return

        if not selected:
            return
        self._video_path = Path(selected)
        self._output_path = self._video_path.with_suffix(".vtt")
        self.has_video = True
        self.selected_file = str(self._video_path)
        self.output_file = str(self._output_path)
        self.status = "Ready"
        self.status_kind = "idle"

    @slint.callback()
    def choose_output(self) -> None:
        if self._video_path is None:
            self.status = "Choose a video first"
            return
        try:
            from tkinter import Tk, filedialog

            root = Tk()
            root.withdraw()
            selected = filedialog.asksaveasfilename(
                title="Save subtitles",
                initialfile=self._video_path.with_suffix(".vtt").name,
                defaultextension=".vtt",
                filetypes=[("WebVTT subtitles", "*.vtt")],
            )
            root.destroy()
        except Exception as error:
            self.status = f"Could not open save dialog: {error}"
            self.status_kind = "error"
            return

        if selected:
            self._output_path = Path(selected)
            self.output_file = str(self._output_path)

    @slint.callback()
    async def start_transcription(self) -> None:
        if self._transcription_running:
            return
        if self._video_path is None:
            self.status = "Choose a video first"
            self.status_kind = "error"
            return

        video_path = self._video_path
        output_path = self._output_path or video_path.with_suffix(".vtt")
        self._transcription_running = True
        self._cancel_event.clear()
        self.busy = True
        self.progress = 0.0
        self.status = "Starting transcription"
        self.status_kind = "busy"
        try:
            task = asyncio.create_task(asyncio.to_thread(
                self._transcribe,
                video_path,
                output_path,
                self.language or None,
                self.model,
                self._cancel_event,
            ))
            while not task.done():
                self.update_progress()
                await asyncio.sleep(0.1)
            await task
            self.update_progress()
            self._document = task.result()
            rows = [
                {
                    "start": _format_timestamp(cue.start_seconds),
                    "finish": _format_timestamp(cue.end_seconds),
                    "text": cue.text,
                }
                for cue in self._document.cues
            ]
            self._segment_model = slint.ListModel(rows)
            self.segments = self._segment_model
            self.has_segments = bool(self._document.cues)
            self.status = f"Saved: {output_path}"
            self.status_kind = "success"
            self.progress = 1.0
        except TranscriptionCancelled:
            self.status = "Transcription cancelled"
            self.status_kind = "idle"
        except Exception as error:
            self.status = f"Transcription failed: {error}"
            self.status_kind = "error"
        finally:
            self._transcription_running = False
            self.busy = False

    @slint.callback()
    def cancel_transcription(self) -> None:
        if self._transcription_running:
            self.status = "Cancelling..."
            self.status_kind = "busy"
            self._cancel_event.set()

    @slint.callback()
    def edit_segment(self, index: int, text: str) -> None:
        if self._document is None or not text.strip() or not 0 <= index < len(self._document.cues):
            return
        cues = list(self._document.cues)
        cue = cues[index]
        cues[index] = SubtitleCue(cue.start_seconds, cue.end_seconds, text)
        self._document = SubtitleDocument(tuple(cues))
        if self._segment_model is not None:
            row = self._segment_model.row_data(index)
            if isinstance(row, dict):
                self._segment_model.set_row_data(index, {**row, "text": text})
        self.status = "Unsaved subtitle edits"
        self.status_kind = "idle"

    @slint.callback()
    def save_edits(self) -> None:
        if self._document is None or self._output_path is None:
            return
        from .infrastructure import WebVttWriter

        WebVttWriter().write(self._document, self._output_path)
        self.status = f"Saved: {self._output_path}"
        self.status_kind = "success"

    def _transcribe(
        self,
        video_path: Path,
        output_path: Path,
        language: str | None,
        model: str,
        cancellation: Event,
    ) -> SubtitleDocument:
        from .application import ProgressReporter, TranscribeVideo
        from .infrastructure import FasterWhisperTranscriber, FfmpegAudioExtractor, WebVttWriter

        app = self

        class QueueReporter(ProgressReporter):
            def report(self, value: float, message: str) -> None:
                app._progress.put((value, message))

        return TranscribeVideo(
            FfmpegAudioExtractor(),
            FasterWhisperTranscriber(model_size=model),
            WebVttWriter(),
        ).execute(
            video_path,
            output_path,
            language,
            QueueReporter(),
            EventCancellation(cancellation),
        )

    def update_progress(self) -> None:
        while True:
            try:
                value, message = self._progress.get_nowait()
            except Empty:
                return
            self.progress = value
            self.status = message


class EventCancellation:
    def __init__(self, event: Event) -> None:
        self._event = event

    def is_cancelled(self) -> bool:
        return self._event.is_set()


def _format_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02}.{milliseconds:03}"


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
