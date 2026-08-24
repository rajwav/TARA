import re
import os
import logging
import subprocess
import shutil
from typing import Optional

logger = logging.getLogger("tara.audio")


class TTSEngine:
    """Text-to-Speech engine supporting Piper TTS with macOS native 'say' fallback."""

    def __init__(self, voice: str = "Samantha"):
        self.voice = voice
        self.piper_bin = shutil.which("piper") or shutil.which("piper-tts")
        self.is_macos = os.uname().sysname == "Darwin"
        self.current_process: Optional[subprocess.Popen] = None
        logger.info(f"TTS Engine initialized (macOS say: {self.is_macos}, Piper: {bool(self.piper_bin)})")

    def _clean_text_for_speech(self, text: str) -> str:
        """Strip markdown syntax, URLs, and code blocks for smooth speech output."""
        clean = re.sub(r"```[\s\S]*?```", "", text)
        clean = re.sub(r"`[^`]*`", "", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
        clean = re.sub(r"[#*_~>|]", " ", clean)
        clean = re.sub(r"http\S+", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def stop(self) -> None:
        """Stop any active speech playback process."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=1.0)
            except Exception:
                pass
            self.current_process = None

    def speak(self, text: str, non_blocking: bool = False) -> None:
        """Speak text aloud using the best available engine."""
        self.stop()
        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            return

        logger.info(f"Speaking: '{clean_text[:60]}...'")

        # 1. Primary on macOS: native 'say' utility (0 RAM, instant, high-quality)
        if self.is_macos:
            try:
                cmd = ["say", "-v", self.voice, clean_text]
                if non_blocking:
                    self.current_process = subprocess.Popen(cmd)
                else:
                    self.current_process = subprocess.Popen(cmd)
                    self.current_process.wait(timeout=30)
                    self.current_process = None
                return
            except Exception as e:
                logger.warning(f"macOS 'say' failed: {e}. Trying fallback.")

        # 2. Piper TTS fallback if installed
        if self.piper_bin:
            try:
                cmd = f'echo "{clean_text}" | {self.piper_bin} --output-raw | afplay -r 22050 -f WAVE'
                subprocess.run(cmd, shell=True, timeout=30)
                return
            except Exception as e:
                logger.warning(f"Piper TTS failed: {e}")

        logger.info(f"[TTS Fallback Console]: {clean_text}")

    def speak_stream(self, text_generator, on_chunk=None) -> str:
        """
        Consume a generator of streaming text chunks, buffer into complete sentences,
        and speak each sentence immediately as soon as complete.
        Returns the full concatenated response text.
        """
        full_text = []
        sentence_buffer = ""
        # Delimiters: sentence punctuation, newlines, or colon/semicolon followed by space
        sentence_delimiters = re.compile(r"([.!?\n]+)")

        try:
            for chunk in text_generator:
                if not chunk:
                    continue
                full_text.append(chunk)
                if on_chunk:
                    on_chunk(chunk)
                sentence_buffer += chunk

                # Check if buffer contains completed sentence delimiter
                parts = sentence_delimiters.split(sentence_buffer)
                if len(parts) > 2:
                    # Everything up to the last split part is complete sentence(s)
                    complete_sentence = "".join(parts[:-1])
                    sentence_buffer = parts[-1]
                    clean_sent = self._clean_text_for_speech(complete_sentence)
                    if clean_sent:
                        self.speak(clean_sent, non_blocking=False)

            # Flush remaining buffer text
            if sentence_buffer.strip():
                clean_remainder = self._clean_text_for_speech(sentence_buffer)
                if clean_remainder:
                    self.speak(clean_remainder, non_blocking=False)

        except (KeyboardInterrupt, Exception) as e:
            self.stop()
            if isinstance(e, KeyboardInterrupt):
                raise

        return "".join(full_text)


class STTEngine:
    """Speech-to-Text engine powered by Faster-Whisper with Voice Activity Detection (VAD)."""

    def __init__(self, model_size: str = "tiny.en"):
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        """Lazy load Faster-Whisper model into memory on first use."""
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Faster-Whisper '{self.model_size}' (int8 on CPU)...")
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=4
            )
            logger.info("Faster-Whisper model loaded successfully.")
        return self._model

    def record_audio_vad(
        self,
        sample_rate: int = 16000,
        silence_timeout: float = 0.8,
        max_duration: float = 10.0,
        energy_threshold: Optional[float] = None
    ):
        """
        Record audio dynamically using adaptive Voice Activity Detection (VAD).
        - Calibrates to ambient noise baseline.
        - Detects speech start.
        - Stops automatically after silence_timeout seconds of trailing silence.
        - Caps at max_duration seconds.
        """
        try:
            import sounddevice as sd
            import numpy as np

            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            if not has_input:
                logger.warning("No microphone input device found.")
                return None

            block_size = 512  # ~32ms per frame at 16kHz
            frames = []
            speech_started = False
            silence_frames = 0
            silence_limit = int((silence_timeout * sample_rate) / block_size)
            max_frames = int((max_duration * sample_rate) / block_size)

            # Calibrate ambient noise floor over first 150ms (~5 frames)
            calibration_frames = 5
            ambient_energies = []

            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size) as stream:
                for _ in range(calibration_frames):
                    data, _ = stream.read(block_size)
                    rms = np.sqrt(np.mean(data**2))
                    ambient_energies.append(rms)

                baseline = float(np.median(ambient_energies)) if ambient_energies else 0.005
                threshold = energy_threshold or max(baseline * 2.5, 0.015)
                logger.debug(f"VAD Calibrated: baseline={baseline:.5f}, threshold={threshold:.5f}")

                for _ in range(max_frames):
                    data, _ = stream.read(block_size)
                    rms = np.sqrt(np.mean(data**2))
                    frames.append(data.copy())

                    if rms > threshold:
                        speech_started = True
                        silence_frames = 0
                    else:
                        if speech_started:
                            silence_frames += 1
                            if silence_frames >= silence_limit:
                                logger.info(f"VAD: Silence detected ({silence_timeout}s). Auto-stopping recording.")
                                break

            if not frames:
                return None

            return np.concatenate(frames).flatten()
        except Exception as e:
            logger.error(f"VAD recording failed: {e}")
            return None

    def record_audio(
        self,
        duration: Optional[float] = None,
        sample_rate: int = 16000,
        silence_timeout: float = 0.8
    ):
        """Record audio. Uses dynamic VAD silence detection by default or fixed duration if specified."""
        if duration is not None:
            # Fixed duration recording mode
            try:
                import sounddevice as sd
                import numpy as np

                devices = sd.query_devices()
                has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
                if not has_input:
                    logger.warning("No microphone input device found.")
                    return None

                logger.info(f"Recording {duration}s fixed audio at {sample_rate}Hz...")
                audio = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32"
                )
                sd.wait()
                return audio.flatten()
            except Exception as e:
                logger.error(f"Microphone recording error: {e}")
                return None
            finally:
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception:
                    pass
        else:
            # Dynamic VAD mode
            return self.record_audio_vad(sample_rate=sample_rate, silence_timeout=silence_timeout)

    def transcribe(self, audio_data) -> str:
        """Transcribe float32 audio array or audio file path into text."""
        if audio_data is None:
            return ""
        if isinstance(audio_data, str) and not audio_data.strip():
            return ""
        if hasattr(audio_data, "__len__") and len(audio_data) == 0:
            return ""

        try:
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=1,
                language="en",
                vad_filter=True
            )
            transcription = " ".join(seg.text for seg in segments).strip()
            if transcription:
                logger.info(f"Transcription complete: '{transcription}'")
            else:
                logger.info("No discernible speech detected in audio.")
            return transcription
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            return ""
