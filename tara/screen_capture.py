import os
import time
import logging
import tempfile
import subprocess
from typing import Optional

logger = logging.getLogger("tara.vision")


class ScreenCapture:
    """
    Lightweight, on-demand screen capture using native macOS utilities.
    Zero background daemons, automatic temporary file cleanup.
    """

    def __init__(self):
        self.is_macos = os.uname().sysname == "Darwin"

    def capture_screen(self, output_path: Optional[str] = None) -> Optional[str]:
        """
        Capture the current active screen to a temporary PNG file.
        Returns the absolute path to the captured screenshot, or None on failure.
        """
        if not output_path:
            fd, output_path = tempfile.mkstemp(prefix="tara_screen_", suffix=".png")
            os.close(fd)

        if self.is_macos:
            try:
                # -x: mute sound, -C: capture cursor
                result = subprocess.run(
                    ["screencapture", "-x", output_path],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Screen captured successfully: {output_path} ({os.path.getsize(output_path)} bytes)")
                    return output_path
                else:
                    logger.warning(f"Native screencapture returned code {result.returncode}. stderr: {result.stderr.decode('utf-8', errors='ignore')}")
            except Exception as e:
                logger.error(f"Error during screen capture: {e}")

        # If native capture failed or not on macOS, check if file exists
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        # Cleanup empty allocated file on failure
        self.cleanup(output_path)
        return None

    def cleanup(self, file_path: Optional[str]) -> None:
        """Safely delete temporary screenshot file to preserve privacy and memory."""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary screen capture: {file_path}")
            except Exception as e:
                logger.debug(f"Failed to remove temporary screenshot {file_path}: {e}")
