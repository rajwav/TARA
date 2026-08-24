import time
import logging
from typing import Optional, Any
from tara.memory import MemoryStore

logger = logging.getLogger("tara.knowledge")


class KnowledgeManager:
    """
    Lightweight, in-memory session document context manager.
    Enforces privacy and prevents storing raw document bodies permanently in SQLite.
    """

    def __init__(self, memory_store: Optional[MemoryStore] = None):
        self.memory = memory_store or MemoryStore()
        self._active_doc: Optional[dict[str, Any]] = None

    def set_active_document(self, path: str, content: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Store active document context in memory for the duration of the session."""
        self._active_doc = {
            "path": path,
            "filename": path.split("/")[-1],
            "content": content,
            "metadata": metadata or {},
            "loaded_at": time.time()
        }
        logger.info(f"Loaded active document into session memory: {self._active_doc['filename']}")

    def get_active_document(self) -> Optional[dict[str, Any]]:
        """Retrieve the currently loaded session document."""
        return self._active_doc

    def clear_context(self) -> None:
        """Clear active document from session memory."""
        self._active_doc = None
        logger.info("Cleared active document context.")

    def save_learned_fact(self, category: str, key: str, value: str) -> dict[str, Any]:
        """
        Store an explicitly requested learned fact or user preference derived from a document into SQLite memory.
        Raw document bodies are strictly excluded.
        """
        if not value or len(value) > 500:
            return {"action": "rejected", "reason": "Fact too large or empty to store in long-term memory."}

        return self.memory.save_fact_safe(category, key, value)
