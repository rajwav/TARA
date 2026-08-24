import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Config:
    # LLM Settings
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()
    default_provider: str = os.getenv("DEFAULT_LLM_PROVIDER", "groq").strip().lower()

    # Paths & Storage
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    db_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/tara.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    def __post_init__(self):
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.setup_logging()

    def setup_logging(self):
        level = getattr(logging, self.log_level, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            force=True
        )

    def validate(self) -> dict[str, bool]:
        """Validate environment readiness."""
        logger = logging.getLogger("tara.config")
        status = {
            "groq_configured": bool(self.groq_api_key and self.groq_api_key != "your_groq_api_key_here"),
            "data_dir_ready": self.data_dir.exists(),
        }

        if not status["groq_configured"] and self.default_provider == "groq":
            logger.warning("GROQ_API_KEY not found or unconfigured. TARA will attempt local Ollama fallback.")

        return status


# Singleton instance
config = Config()
