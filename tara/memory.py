import re
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager
from tara.config import config

logger = logging.getLogger("tara.memory")


class MemoryStore:
    """Safe, non-destructive, intelligent SQLite memory store for TARA."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Yield a managed SQLite connection and ensure it is closed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize SQLite schema with safe non-destructive tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Messages table (conversation turns)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Safe User Facts table (preserves history, allows multi-value & archiving)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Episodic Conversation Summaries table (compact narrative memory of older turns)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    last_summarized_msg_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Temporary Conversation State (session-scoped emotional context, never persisted to user_facts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    emotion TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def save_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a conversation turn."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()

    def get_recent_messages(self, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        """Retrieve recent conversation history for active context window."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit)
            )
            return [{"role": row["role"], "content": row["content"]} for row in cursor.fetchall()]

    def save_conversation_emotion(self, session_id: str, emotion: str, confidence: float) -> None:
        """Persist session-level temporary emotional state."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversation_state (session_id, emotion, confidence) VALUES (?, ?, ?)",
                (session_id, emotion, confidence)
            )
            conn.commit()

    def get_latest_emotion(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve the most recent emotional state for the active session."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT emotion, confidence, timestamp FROM conversation_state WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,)
            ).fetchone()
            if row:
                return {
                    "emotion": row["emotion"],
                    "confidence": row["confidence"],
                    "timestamp": row["timestamp"]
                }
            return None

    def get_episodic_summary(self, session_id: str) -> Optional[str]:
        """Retrieve current episodic summary for a given session."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT summary FROM conversation_summaries WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return row["summary"] if row else None

    def get_unsummarized_messages(self, session_id: str, keep_recent: int = 6) -> tuple[list[dict[str, Any]], int, Optional[str]]:
        """
        Retrieve messages older than the keep_recent window that have not yet been summarized.
        Returns: (unsummarized_messages_list, max_msg_id, existing_summary)
        """
        with self._get_connection() as conn:
            sum_row = conn.execute(
                "SELECT summary, last_summarized_msg_id FROM conversation_summaries WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            existing_summary = sum_row["summary"] if sum_row else None
            last_id = sum_row["last_summarized_msg_id"] if sum_row else 0

            rows = conn.execute(
                "SELECT id, role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            ).fetchall()

            if len(rows) <= keep_recent:
                return [], last_id, existing_summary

            older_rows = rows[:-keep_recent]
            unsummarized = [
                {"id": r["id"], "role": r["role"], "content": r["content"]}
                for r in older_rows if r["id"] > last_id
            ]

            max_id = unsummarized[-1]["id"] if unsummarized else last_id
            return unsummarized, max_id, existing_summary

    def save_episodic_summary(self, session_id: str, summary: str, last_summarized_msg_id: int) -> None:
        """Persist or update the episodic summary for a session."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_summaries (session_id, summary, last_summarized_msg_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary = excluded.summary,
                    last_summarized_msg_id = excluded.last_summarized_msg_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session_id, summary.strip(), last_summarized_msg_id)
            )
            conn.commit()
            logger.info(f"Saved episodic summary for session '{session_id}' up to msg_id {last_summarized_msg_id}")

    def classify_importance(self, text: str) -> str:
        """
        Classify input for memory retention:
        - 'IGNORE': Transient status, ephemeral feelings/events, or tool commands.
        - 'ASK_CONFIRMATION': Identity changes conflicting with known state.
        - 'REMEMBER': Long-term user preferences, projects, habits, achievements, or facts.
        """
        clean = text.strip().lower()

        # 1. Ephemeral states, commands, questions, and document/workspace queries to ignore
        ephemeral_patterns = [
            r"\b(?:i am|i'm)\s+(?:eating|having lunch|having dinner|drinking|going to|heading to|walking to|leaving for)\b",
            r"\b(?:right now|currently right now|at the moment)\s+(?:i am|i'm|it is|it's)\b",
            r"\b(?:today i will|just bought|feeling tired|hungry|sleepy|bored|feeling frustrated|frustrated today)\b",
            r"\b(?:what time|what is the time|battery status|check battery|open|search)\b",
            r"\b(?:fixed a typo|corrected a typo|small fix|typo in)\b",
            r"\b(?:summarize|read document|read file|analyze document|analyze screen|search workspace|look at|search for|find file|find my notes)\b",
            r"\b(?:what does|how does|can you|could you|explain|tell me about|what is|where is|which file)\b",
        ]
        for pattern in ephemeral_patterns:
            if re.search(pattern, clean):
                return "IGNORE"

        # Questions are never facts to remember
        if clean.endswith("?"):
            return "IGNORE"

        # 2. Check for identity conflict that requires confirmation
        name_match = re.search(r"\b(?:my name is|i am called|call me)\s+([A-Za-z]+)", text, re.IGNORECASE)
        if name_match:
            new_name = name_match.group(1).capitalize()
            with self._get_connection() as conn:
                existing = conn.execute(
                    "SELECT value FROM user_facts WHERE category = 'identity' AND key = 'name' AND status = 'active'"
                ).fetchone()
                if existing and existing["value"].lower() != new_name.lower():
                    return "ASK_CONFIRMATION"

        # 3. Explicit first-person long-term memory statements only
        long_term_patterns = [
            r"^(?:remember that\s+)?(?:my name is|call me)\s+[a-z]+",
            r"^(?:remember that\s+)?(?:my current project is|my project is|i am building|i'm building|working on project)\s+",
            r"^(?:remember that\s+)?(?:i prefer|i usually use|i typically use|i mostly work with|my favorite|i like|i love|i don't like|i avoid)\s+",
            r"^(?:remember that\s+)?(?:my goal is to|i want to build|disable proactive|enable proactive|turn off proactive|turn on proactive)\b",
            r"^(?:remember that\s+)?(?:(?:i (?:have )?)?(?:completed|finished building|successfully built|successfully deployed|shipped|launched))\s+",
        ]
        for pattern in long_term_patterns:
            if re.search(pattern, clean):
                return "REMEMBER"

        return "IGNORE"

    def save_fact_safe(self, category: str, key: str, value: str) -> dict[str, Any]:
        """
        Safely store a user fact using human-like memory semantics:
        - Project: archive previous project instead of deleting; reactivate if returning.
        - Preference / Habit / Dislike / Achievement: additive without duplicates.
        - Identity (e.g. name): detects conflicts without overwriting.
        """
        key_norm = key.strip().lower()
        val_norm = value.strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Case 1: Identity conflict check (e.g. Name)
            if category == "identity" and key_norm == "name":
                cursor.execute(
                    "SELECT id, value FROM user_facts WHERE category = 'identity' AND key = 'name' AND status = 'active'"
                )
                existing = cursor.fetchone()
                if existing:
                    if existing["value"].lower() != val_norm.lower():
                        logger.info(f"Name conflict detected: existing='{existing['value']}', new='{val_norm}'")
                        return {
                            "action": "conflict",
                            "key": "name",
                            "existing_value": existing["value"],
                            "new_value": val_norm,
                            "message": f"I previously had your name as {existing['value']}. Should I update it to {val_norm}?"
                        }
                    return {"action": "noop", "key": "name", "value": existing["value"]}

            # Case 2: Project State Transitions (A -> B -> C -> B)
            if category == "project" and key_norm == "current_project":
                cursor.execute(
                    "SELECT id, value FROM user_facts WHERE category = 'project' AND key = 'current_project' AND status = 'active'"
                )
                existing = cursor.fetchone()

                if existing:
                    if existing["value"].lower() == val_norm.lower():
                        return {"action": "noop", "key": "current_project", "value": existing["value"]}

                    # Archive current active project
                    cursor.execute(
                        """
                        UPDATE user_facts 
                        SET key = 'previous_project', status = 'archived', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (existing["id"],)
                    )

                # Reactivate if previously archived, or insert new
                cursor.execute(
                    "SELECT id FROM user_facts WHERE category = 'project' AND LOWER(value) = LOWER(?) AND status = 'archived'",
                    (val_norm,)
                )
                archived_row = cursor.fetchone()
                if archived_row:
                    cursor.execute(
                        """
                        UPDATE user_facts 
                        SET key = 'current_project', status = 'active', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (archived_row["id"],)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO user_facts (category, key, value, status) VALUES ('project', 'current_project', ?, 'active')",
                        (val_norm,)
                    )

                conn.commit()
                archived_val = existing["value"] if existing else None
                logger.info(f"Project transition: archived='{archived_val}', current='{val_norm}'")
                return {"action": "transition", "archived": archived_val, "current": val_norm}

            # Case 3: Additive Multi-Value Memory (Preferences, Habits, Dislikes, Achievements)
            if category in ("preference", "habit", "dislike", "achievement"):
                cursor.execute(
                    "SELECT id FROM user_facts WHERE category = ? AND LOWER(value) = LOWER(?) AND status = 'active'",
                    (category, val_norm)
                )
                if cursor.fetchone():
                    return {"action": "noop", "key": key_norm, "value": val_norm}

                cursor.execute(
                    "INSERT INTO user_facts (category, key, value, status) VALUES (?, ?, ?, 'active')",
                    (category, key_norm, val_norm)
                )
                conn.commit()
                logger.info(f"Added new {category}: {val_norm}")
                return {"action": "added", "key": key_norm, "value": val_norm}

            # Case 4: General / Goals
            cursor.execute(
                "SELECT id FROM user_facts WHERE category = ? AND key = ? AND LOWER(value) = LOWER(?) AND status = 'active'",
                (category, key_norm, val_norm)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO user_facts (category, key, value, status) VALUES (?, ?, ?, 'active')",
                    (category, key_norm, val_norm)
                )
                conn.commit()
                return {"action": "added", "key": key_norm, "value": val_norm}

            return {"action": "noop", "key": key_norm, "value": val_norm}

    def confirm_update_fact(self, category: str, key: str, new_value: str) -> None:
        """Explicitly confirm and apply an update, archiving previous values."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE user_facts SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE category = ? AND key = ? AND status = 'active'",
                (category, key.strip().lower())
            )
            conn.execute(
                "INSERT INTO user_facts (category, key, value, status) VALUES (?, ?, ?, 'active')",
                (category, key.strip().lower(), new_value.strip())
            )
            conn.commit()
            logger.info(f"Confirmed update for {category}.{key} -> {new_value}")

    def get_all_facts(self) -> dict[str, Any]:
        """Fetch all facts structured by category and status, prioritizing active state."""
        facts: dict[str, Any] = {
            "name": None,
            "current_project": None,
            "previous_projects": [],
            "preferences": [],
            "habits": [],
            "dislikes": [],
            "goals": [],
            "achievements": [],
            "general": {}
        }
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT category, key, value, status FROM user_facts ORDER BY id ASC"
            )
            for row in cursor.fetchall():
                cat, k, v, status = row["category"], row["key"], row["value"], row["status"]
                if cat == "identity" and k == "name" and status == "active":
                    facts["name"] = v
                elif cat == "project":
                    if k == "current_project" and status == "active":
                        facts["current_project"] = v
                    elif (k in ("previous_project", "project") or status == "archived") and v:
                        if v not in facts["previous_projects"]:
                            facts["previous_projects"].append(v)
                elif cat == "preference" and status == "active":
                    if v not in facts["preferences"]:
                        facts["preferences"].append(v)
                elif cat == "habit" and status == "active":
                    if v not in facts["habits"]:
                        facts["habits"].append(v)
                elif cat == "dislike" and status == "active":
                    if v not in facts["dislikes"]:
                        facts["dislikes"].append(v)
                elif cat == "goal" and status == "active":
                    if v not in facts["goals"]:
                        facts["goals"].append(v)
                elif cat == "achievement" and status == "active":
                    if v not in facts["achievements"]:
                        facts["achievements"].append(v)
                elif status == "active":
                    facts["general"][k] = v

            # Ensure active current_project is never in previous_projects
            if facts["current_project"] and facts["current_project"] in facts["previous_projects"]:
                facts["previous_projects"].remove(facts["current_project"])

        return facts

    def extract_and_save_facts(self, text: str) -> list[dict[str, Any]]:
        """Extract personal facts using natural language rules with importance filtering."""
        results: list[dict[str, Any]] = []
        clean_text = text.strip()

        # Step 0: Check memory importance (ignore transient/ephemeral status)
        importance = self.classify_importance(clean_text)
        if importance == "IGNORE":
            return results

        # Proactive mode toggle extraction
        if re.search(r"\b(?:disable|turn off|stop|mute)\s+(?:proactive\s+)?reminders?\b", clean_text, re.IGNORECASE):
            res = self.save_fact_safe("general", "proactive_mode", "disabled")
            results.append({"action": "preference_updated", "key": "proactive_mode", "value": "disabled"})
            return results

        if re.search(r"\b(?:enable|turn on|activate|resume)\s+(?:proactive\s+)?reminders?\b", clean_text, re.IGNORECASE):
            res = self.save_fact_safe("general", "proactive_mode", "enabled")
            results.append({"action": "preference_updated", "key": "proactive_mode", "value": "enabled"})
            return results

        # Meaningful Achievement extraction (e.g. "I completed Phase 6.4 of TARA", "Finished building wake word system")
        achieve_match = re.search(
            r"\b(?:(?:i (?:have )?)?(?:completed|finished building|launched|shipped|built)|successfully (?:built|deployed|implemented))\s+(?:the\s+)?(.+?)(?:$|[!?,;]|\.\s)",
            clean_text,
            re.IGNORECASE
        )
        if achieve_match:
            milestone = achieve_match.group(1).strip()
            # Ignore trivial fixes like "fixed a typo"
            if not re.search(r"\b(?:typo|small fix|spelling)\b", milestone, re.IGNORECASE):
                res = self.save_fact_safe("achievement", "milestone", milestone)
                results.append(res)

        # Explicit update confirmation (e.g. "Yes update my name to Rahul", "Update name to Rahul")
        confirm_match = re.search(r"\b(?:yes\s+)?(?:please\s+)?update\s+(?:my\s+)?name\s+to\s+([A-Za-z]+)", clean_text, re.IGNORECASE)
        if confirm_match:
            new_name = confirm_match.group(1).capitalize()
            self.confirm_update_fact("identity", "name", new_name)
            results.append({"action": "confirmed_update", "key": "name", "value": new_name})
            return results

        # 1. Name extraction
        name_match = re.search(r"\b(?:my name is|i am called|call me)\s+([A-Za-z]+)", clean_text, re.IGNORECASE)
        if name_match:
            res = self.save_fact_safe("identity", "name", name_match.group(1).capitalize())
            results.append(res)

        # 2. Project extraction
        project_match = re.search(
            r"\b(?:my current project is|i am building|i'm building|working on project|my project is)\s+([^,\.!?]+)",
            clean_text,
            re.IGNORECASE
        )
        if project_match:
            res = self.save_fact_safe("project", "current_project", project_match.group(1).strip())
            results.append(res)

        # 3. Natural Language Preferences
        # "I usually use VS Code" / "I typically work with React" / "I use VS Code"
        usage_match = re.search(r"\b(?:i usually use|i typically use|i mostly work with|i use)\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if usage_match:
            res = self.save_fact_safe("preference", "workflow", usage_match.group(1).strip())
            results.append(res)

        # "I prefer Python for projects" / "I prefer Python"
        pref_for_match = re.search(r"\bi prefer\s+([^,\.!?]+?)(?:\s+for\s+([^,\.!?]+))?$", clean_text, re.IGNORECASE)
        if pref_for_match and not usage_match:
            item = pref_for_match.group(1).strip()
            context = f" for {pref_for_match.group(2).strip()}" if pref_for_match.group(2) else ""
            res = self.save_fact_safe("preference", "preference", f"{item}{context}")
            results.append(res)

        # "My favorite framework is FastAPI"
        fav_match = re.search(r"\b(?:my favorite|my preferred)\s+([a-zA-Z0-9_\s]+?)\s+is\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if fav_match:
            key = f"favorite_{fav_match.group(1).strip().replace(' ', '_').lower()}"
            res = self.save_fact_safe("preference", key, fav_match.group(2).strip())
            results.append(res)

        # "I like Python" / "I love Rust" / "I enjoy using Docker" / "I like coffee"
        like_match = re.search(r"\b(?:i like|i love|i enjoy using)\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if like_match and not fav_match and not usage_match:
            res = self.save_fact_safe("preference", "likes", like_match.group(1).strip())
            results.append(res)

        # "I don't like Java" / "I avoid PHP"
        dislike_match = re.search(r"\b(?:i don't like|i do not like|i dislike|i avoid)\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if dislike_match:
            res = self.save_fact_safe("dislike", "dislikes", dislike_match.group(1).strip())
            results.append(res)

        # 4. Habits: "I tend to work late at night" / "I always test my code"
        habit_match = re.search(r"\b(?:i tend to|i always|i usually)\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if habit_match and not usage_match:
            res = self.save_fact_safe("habit", "routine", habit_match.group(1).strip())
            results.append(res)

        # 5. Goals
        goal_match = re.search(r"\b(?:my goal is to|i want to|aiming to)\s+([^,\.!?]+)", clean_text, re.IGNORECASE)
        if goal_match:
            res = self.save_fact_safe("goal", "primary_goal", goal_match.group(1).strip())
            results.append(res)

        return results
