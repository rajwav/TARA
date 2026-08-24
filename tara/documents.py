import os
import logging
from pathlib import Path
from typing import Optional, Any
from tara.llm import LLMClient

logger = logging.getLogger("tara.documents")


class DocumentEngine:
    """
    Lightweight, high-performance document processor for TARA.
    Supports PDF, TXT, Markdown, JSON, YAML, and source code files without heavy frameworks.
    """

    SUPPORTED_CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml",
        ".sh", ".bash", ".zsh", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".sql", ".rb",
        ".java", ".php", ".xml", ".csv", ".ini", ".conf", ".env", ".toml"
    }

    def __init__(self):
        self.llm = LLMClient()

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative or absolute file path against workspace root."""
        from tara.config import config
        if not path or not path.strip():
            raise FileNotFoundError("Empty document path provided.")

        p = Path(path.strip())
        if p.is_absolute() and p.exists():
            return p

        # Check relative to cwd
        if p.exists():
            return p.resolve()

        # Check relative to workspace base_dir
        base_p = (config.base_dir / p).resolve()
        if base_p.exists():
            return base_p

        raise FileNotFoundError(f"Document file not found: '{path}' (searched workspace: {config.base_dir})")

    def extract_text(self, path: str, max_chars: int = 50000) -> str:
        """
        Extract plain text content from PDF, text, markdown, or source code files.
        """
        file_path = self._resolve_path(path)
        ext = file_path.suffix.lower()

        # 1. PDF Extraction
        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                text_parts = []
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"--- Page {i + 1} ---\n{page_text.strip()}")
                extracted = "\n\n".join(text_parts)
                if not extracted.strip():
                    return "[Note: PDF contains no extractable text or consists solely of scanned images.]"
                if len(extracted) > max_chars:
                    return extracted[:max_chars] + f"\n\n[Content truncated at {max_chars} characters...]"
                return extracted
            except Exception as e:
                logger.error(f"PDF extraction error for {path}: {e}")
                raise RuntimeError(f"Failed to extract PDF text: {e}")

        # 2. Text, Markdown, and Code Files
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars + 1)

            if len(content) > max_chars:
                return content[:max_chars] + f"\n\n[Content truncated at {max_chars} characters...]"
            return content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise RuntimeError(f"Failed to read file: {e}")

    def load_document(self, path: str) -> dict[str, Any]:
        """
        Inspect and load document metadata and preview.
        """
        if not path or not os.path.exists(path):
            return {
                "success": False,
                "error": f"File not found: {path}"
            }

        file_path = Path(path)
        size_bytes = os.path.getsize(path)
        ext = file_path.suffix.lower()

        try:
            text = self.extract_text(path, max_chars=1000)
            return {
                "success": True,
                "path": str(file_path.resolve()),
                "filename": file_path.name,
                "format": ext,
                "size_bytes": size_bytes,
                "char_count": len(text),
                "preview": text[:300]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def summarize_document(self, path: str) -> str:
        """
        Generate a concise, high-density summary of a document.
        """
        try:
            content = self.extract_text(path, max_chars=30000)
            filename = Path(path).name
            prompt = [
                {
                    "role": "system",
                    "content": "You are an expert technical summarizer. Extract key ideas, decisions, architecture, and takeaways concisely."
                },
                {
                    "role": "user",
                    "content": f"Summarize the following document ('{filename}') in a structured, bulleted format:\n\n{content}"
                }
            ]
            summary = self.llm.generate(prompt)
            return summary or "Unable to generate summary."
        except Exception as e:
            return f"Error summarizing document: {e}"

    def answer_from_document(self, path: str, question: str) -> str:
        """
        Answer a specific question grounded strictly in the provided document content.
        """
        try:
            content = self.extract_text(path, max_chars=30000)
            filename = Path(path).name
            prompt = [
                {
                    "role": "system",
                    "content": "You are TARA, answering questions grounded accurately in the provided document. Cite relevant sections when appropriate."
                },
                {
                    "role": "user",
                    "content": f"Document ('{filename}'):\n{content}\n\nQuestion: {question}"
                }
            ]
            reply = self.llm.generate(prompt)
            return reply or "Unable to answer from document."
        except Exception as e:
            return f"Error analyzing document: {e}"
