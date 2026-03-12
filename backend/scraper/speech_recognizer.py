import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """Transcribe video audio using faster-whisper (lazy-loaded)."""

    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("Loading whisper model (base, int8)...")
                cls._model = WhisperModel("base", device="cpu", compute_type="int8")
                logger.info("Whisper model loaded")
            except ImportError:
                logger.error("faster-whisper not installed. Run: pip install faster-whisper")
                raise
        return cls._model

    @staticmethod
    def _extract_audio(video_path: str) -> str | None:
        """Extract audio from video using ffmpeg to a temp WAV file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1",
                    tmp.name,
                ],
                capture_output=True, timeout=120,
            )
            if result.returncode != 0:
                logger.warning(f"ffmpeg failed: {result.stderr.decode()[:200]}")
                os.unlink(tmp.name)
                return None
            return tmp.name
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install: brew install ffmpeg")
            os.unlink(tmp.name)
            return None
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg timed out")
            os.unlink(tmp.name)
            return None

    async def recognize(self, video_path: str) -> str | None:
        """Transcribe speech from a video file. Returns text or None."""
        if not Path(video_path).exists():
            logger.warning(f"Video file not found: {video_path}")
            return None

        loop = asyncio.get_running_loop()

        # Extract audio (run in thread to avoid blocking)
        audio_path = await loop.run_in_executor(None, self._extract_audio, video_path)
        if not audio_path:
            return None

        try:
            # Transcribe (run in thread to avoid blocking event loop)
            def _transcribe():
                model = self._get_model()
                segments, info = model.transcribe(audio_path, beam_size=5, language="zh")
                texts = [seg.text.strip() for seg in segments if seg.text.strip()]
                return " ".join(texts) if texts else None

            text = await loop.run_in_executor(None, _transcribe)
            if text:
                logger.info(f"Transcribed {len(text)} chars from {Path(video_path).name}")
            else:
                logger.info(f"No speech detected in {Path(video_path).name}")
            return text

        finally:
            # Clean up temp audio file
            try:
                os.unlink(audio_path)
            except OSError:
                pass
