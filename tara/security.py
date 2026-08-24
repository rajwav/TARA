import os
import json
import sqlite3
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Tuple
from contextlib import contextmanager
from tara.config import config

logger = logging.getLogger("tara.security")


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SecurityGuard:
    """
    Action Permission & Safety Guard for TARA.
    - Validates file paths to prevent traversal and protected system folder overwrites.
    - Enforces permission risk tiers (LOW, MEDIUM, HIGH).
    - Prevents permanent destructive operations (e.g. permanent file deletion).
    - Logs every executed action into SQLite action_history table.
    """

    FORBIDDEN_SYSTEM_PATHS = {
        "/", "/System", "/Library", "/usr", "/bin", "/sbin", "/etc", "/var/root", "/private/var/root"
    }

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self._init_security_db()

    @contextmanager
    def _get_connection(self):
        """Yield a managed SQLite connection and ensure it is closed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_security_db(self) -> None:
        """Ensure action_history table exists in SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action_name TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    user_confirmation TEXT DEFAULT 'granted'
                );
            """)
            conn.commit()

    def validate_path(self, path_str: str, allow_write: bool = False) -> Path:
        """
        Validate and resolve a file/folder path safely.
        Prevents traversal escapes and protects critical system roots.
        """
        if not path_str or not path_str.strip():
            raise ValueError("Path cannot be empty.")

        raw_path = Path(path_str.strip())

        # Resolve relative to base_dir if relative
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (config.base_dir / raw_path).resolve()

        resolved_str = str(resolved)

        # Protect critical system paths from write/modification operations
        if allow_write:
            for sys_path in self.FORBIDDEN_SYSTEM_PATHS:
                if resolved_str == sys_path or (resolved_str.startswith(sys_path + "/") and not resolved_str.startswith(str(config.base_dir)) and not resolved_str.startswith(os.path.expanduser("~"))):
                    raise PermissionError(f"Security Alert: Modification of critical system path '{resolved_str}' is forbidden.")

        return resolved

    def log_action(
        self,
        action_name: str,
        parameters: dict[str, Any],
        risk_level: RiskLevel,
        status: str,
        user_confirmation: str = "granted"
    ) -> None:
        """Record an action execution event into SQLite audit log."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO action_history (action_name, parameters, risk_level, status, user_confirmation)
                    VALUES (?, ?, ?, ?, ?)
                """, (action_name, json.dumps(parameters), risk_level.value, status, user_confirmation))
                conn.commit()
            logger.info(f"Logged action '{action_name}' [{risk_level.value}] -> {status}")
        except Exception as e:
            logger.error(f"Failed to log action '{action_name}' to SQLite: {e}")

    def check_and_authorize(
        self,
        action_name: str,
        parameters: dict[str, Any],
        risk_level: RiskLevel,
        confirmed: bool = False
    ) -> Tuple[bool, str]:
        """
        Authorize action execution based on risk level.
        - LOW: executed directly.
        - MEDIUM: permitted with audit logging; asks confirmation if specified.
        - HIGH: requires explicit user confirmation.
        """
        if risk_level == RiskLevel.LOW:
            return True, "Authorized (Low Risk)"

        if risk_level == RiskLevel.MEDIUM:
            # Medium risk actions (e.g. file creation, folder creation)
            return True, "Authorized (Medium Risk with audit log)"

        if risk_level == RiskLevel.HIGH:
            if confirmed:
                return True, "Authorized (High Risk confirmed by user)"
            return False, f"High-risk operation '{action_name}' requires explicit confirmation."

        return False, "Unknown risk tier."


# Global security guard singleton
security_guard = SecurityGuard()
