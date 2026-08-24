import queue
import logging
import numpy as np
import sounddevice as sd
from typing import Optional, Callable
import openwakeword
from openwakeword.model import Model

logger = logging.getLogger("tara.wakeword")


class WakeWordDetector:
    """
    Lightweight, continuous wake word detector for TARA using openWakeWord and ONNX Runtime.
    Idle resource footprint: < 80 MB RAM, < 3% CPU on Apple Silicon M1.
    """

    def __init__(
        self,
        wakeword_models: Optional[list[str]] = None,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        chunk_size: int = 1280,  # 80ms chunks at 16kHz
        on_wake: Optional[Callable[[], None]] = None
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.on_wake = on_wake
        self._is_running = False

        # Default pre-trained ONNX models
        models_to_load = wakeword_models or ["hey_jarvis", "hey_mycroft"]
        try:
            self.model = Model(wakeword_models=models_to_load)
            logger.info(f"Loaded wake word models: {list(self.model.models.keys())}")
        except Exception as e:
            logger.warning(f"Error loading models ({e}), downloading defaults...")
            openwakeword.utils.download_models()
            self.model = Model(wakeword_models=models_to_load)

    def listen_for_wake(self) -> bool:
        """
        Block and listen on the microphone until a wake word is detected.
        Returns True when wake word is triggered, or False if interrupted / microphone unavailable.
        """
        audio_queue = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio stream status: {status}")
            # indata is float32 [-1.0, 1.0]; scale to 16-bit PCM for openWakeWord
            pcm16 = (indata[:, 0] * 32767).astype(np.int16)
            audio_queue.put(pcm16)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.chunk_size,
                callback=audio_callback
            ):
                self._is_running = True
                self.model.reset()

                while self._is_running:
                    try:
                        chunk = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    # Run ONNX inference on audio frame
                    prediction = self.model.predict(chunk)
                    for mdl_name, score in prediction.items():
                        if score >= self.threshold:
                            logger.info(f"Wake word activated: {mdl_name} (Score: {score:.2f})")
                            self.model.reset()
                            if self.on_wake:
                                self.on_wake()
                            return True

        except Exception as e:
            logger.error(f"Wake word listening error: {e}")
            return False
        finally:
            self._is_running = False

    def predict_audio_buffer(self, audio_data: np.ndarray) -> dict[str, float]:
        """
        Feed an in-memory 16kHz float32 or int16 numpy buffer into the model for testing.
        Returns max score achieved per model across all chunks in the buffer.
        """
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            pcm16 = (audio_data * 32767).astype(np.int16)
        else:
            pcm16 = audio_data.astype(np.int16)

        self.model.reset()
        max_scores: dict[str, float] = {}

        for i in range(0, len(pcm16), self.chunk_size):
            chunk = pcm16[i:i + self.chunk_size]
            if len(chunk) < self.chunk_size:
                chunk = np.pad(chunk, (0, self.chunk_size - len(chunk)))
            scores = self.model.predict(chunk)
            for k, v in scores.items():
                max_scores[k] = max(max_scores.get(k, 0.0), float(v))

        return max_scores

    def stop(self) -> None:
        """Signal the listener loop to stop."""
        self._is_running = False
