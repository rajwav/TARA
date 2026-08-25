import os
import re
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Any
from tara.config import config
from tara.documents import DocumentEngine

logger = logging.getLogger("tara.workspace")

# Common stop words to filter out when generating keyword index
STOP_WORDS = {
    "the", "and", "is", "for", "in", "on", "to", "with", "of", "a", "an", "this", "that",
    "from", "by", "as", "at", "it", "are", "be", "was", "or", "which", "if", "then", "else",
    "self", "import", "return", "def", "class", "from", "while", "true", "false", "none"
}

SUPPORTED_EXTENSIONS = {
    ".py", ".md", ".txt", ".pdf", ".json", ".yaml", ".yml", ".js", ".ts",
    ".html", ".css", ".sh", ".c", ".cpp", ".rs", ".go", ".sql", ".toml", ".csv"
}


class KnowledgeWorkspace:
    """
    Lightweight, privacy-first personal knowledge workspace for TARA.
    Powered by SQLite + FTS5 full-text keyword search.
    Stores metadata and extracted keywords only; raw file bodies are never permanently retained.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self.doc_engine = DocumentEngine()
        self._init_workspace_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_workspace_db(self) -> None:
        """Initialize knowledge_index and FTS5 full-text search index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create FTS5 virtual table for fast full-text ranking
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    path,
                    filename,
                    file_type,
                    keywords,
                    summary,
                    tokenize='porter unicode61'
                );
            """)
            conn.commit()

    def _extract_keywords(self, text: str, max_keywords: int = 35) -> str:
        """Extract high-signal keywords and topics from text content."""
        words = re.findall(r"[A-Za-z0-9_]{3,}", text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if w not in STOP_WORDS and not w.isdigit():
                freq[w] = freq.get(w, 0) + 1

        # Sort by frequency and select top terms
        sorted_terms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top_terms = [k for k, _ in sorted_terms[:max_keywords]]
        return ", ".join(top_terms)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative or absolute file path against workspace root."""
        if not path or not path.strip():
            raise FileNotFoundError("Empty workspace path provided.")

        p = Path(path.strip())
        if p.is_absolute() and p.exists():
            return p.resolve()
        if p.exists():
            return p.resolve()

        base_p = (config.base_dir / p).resolve()
        if base_p.exists():
            return base_p

        return p.resolve()

    def index_file(self, path: str) -> dict[str, Any]:
        """
        Index metadata and extracted keywords of a document/code file into SQLite.
        """
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for indexing: '{path}' (searched workspace: {config.base_dir})")
        ext = file_path.suffix.lower()
        filename = file_path.name

        # Extract text preview and keywords
        try:
            text_preview = self.doc_engine.extract_text(str(file_path), max_chars=12000)
            keywords = self._extract_keywords(text_preview)
            # Create a concise 1-line summary / title
            first_lines = [line.strip("# -* \t") for line in text_preview.split("\n") if line.strip()]
            summary_snippet = first_lines[0][:150] if first_lines else f"{filename} ({ext})"
        except Exception as e:
            logger.warning(f"Could not extract keywords from {path}: {e}")
            keywords = filename
            summary_snippet = f"File {filename}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert into knowledge_index
            cursor.execute("""
                INSERT INTO knowledge_index (path, filename, file_type, keywords, summary, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    filename = excluded.filename,
                    file_type = excluded.file_type,
                    keywords = excluded.keywords,
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(file_path), filename, ext, keywords, summary_snippet))

            # Sync with FTS5 index
            cursor.execute("DELETE FROM knowledge_fts WHERE path = ?", (str(file_path),))
            cursor.execute("""
                INSERT INTO knowledge_fts (path, filename, file_type, keywords, summary)
                VALUES (?, ?, ?, ?, ?)
            """, (str(file_path), filename, ext, keywords, summary_snippet))

            conn.commit()

        logger.info(f"Indexed workspace document: {filename} [{ext}]")
        return {
            "path": str(file_path),
            "filename": filename,
            "file_type": ext,
            "keywords": keywords,
            "summary": summary_snippet
        }

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search the personal knowledge workspace using FTS5 with LIKE fallback.
        """
        if not query or not query.strip():
            return []

        clean_query = re.sub(r"[^\w\s]", "", query.strip())
        results = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Try SQLite FTS5 Match
            if clean_query:
                fts_query = " OR ".join(clean_query.split())
                try:
                    cursor.execute("""
                        SELECT path, filename, file_type, keywords, summary, rank
                        FROM knowledge_fts
                        WHERE knowledge_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """, (fts_query, limit))
                    for row in cursor.fetchall():
                        results.append({
                            "path": row["path"],
                            "filename": row["filename"],
                            "file_type": row["file_type"],
                            "keywords": row["keywords"],
                            "summary": row["summary"]
                        })
                except Exception as e:
                    logger.debug(f"FTS5 search fallback: {e}")

            # 2. Fallback to LIKE search if FTS returned nothing
            if not results:
                like_pattern = f"%{clean_query}%"
                cursor.execute("""
                    SELECT path, filename, file_type, keywords, summary
                    FROM knowledge_index
                    WHERE filename LIKE ? OR keywords LIKE ? OR summary LIKE ?
                    LIMIT ?
                """, (like_pattern, like_pattern, like_pattern, limit))
                for row in cursor.fetchall():
                    results.append({
                        "path": row["path"],
                        "filename": row["filename"],
                        "file_type": row["file_type"],
                        "keywords": row["keywords"],
                        "summary": row["summary"]
                    })

        return results

    def remove_file(self, path: str) -> bool:
        """Remove a file from the knowledge index."""
        resolved_path = str(self._resolve_path(path))
        raw_path = str(Path(path))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge_index WHERE path = ? OR path = ?", (resolved_path, raw_path))
            cursor.execute("DELETE FROM knowledge_fts WHERE path = ? OR path = ?", (resolved_path, raw_path))
            conn.commit()
            deleted = cursor.rowcount > 0
            logger.info(f"Removed from knowledge workspace: {resolved_path} (success: {deleted})")
            return deleted

    def get_workspace_summary(self) -> dict[str, Any]:
        """Return workspace statistics and breakdown of indexed files."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            total_count = cursor.execute("SELECT COUNT(*) as cnt FROM knowledge_index").fetchone()["cnt"]

            type_counts = {}
            for row in cursor.execute("SELECT file_type, COUNT(*) as cnt FROM knowledge_index GROUP BY file_type").fetchall():
                type_counts[row["file_type"]] = row["cnt"]

            recent = [
                {"filename": r["filename"], "path": r["path"], "file_type": r["file_type"]}
                for r in cursor.execute("SELECT filename, path, file_type FROM knowledge_index ORDER BY updated_at DESC LIMIT 5").fetchall()
            ]

            return {
                "total_documents": total_count,
                "file_types": type_counts,
                "recent_documents": recent
            }

    def index_directory(self, dir_path: str = ".", max_files: int = 50) -> int:
        """
        Recursively index all supported documents in a directory (ignoring build & hidden directories).
        """
        ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist", ".gemini", ".idea"}
        indexed_count = 0

        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]

            for f in sorted(files):
                if indexed_count >= max_files:
                    break
                ext = Path(f).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS and not f.startswith("."):
                    full_path = os.path.join(root, f)
                    try:
                        self.index_file(full_path)
                        indexed_count += 1
                    except Exception as e:
                        logger.debug(f"Skipped indexing {full_path}: {e}")

        logger.info(f"Workspace directory scan complete: indexed {indexed_count} files.")
        return indexed_count
