# Memory Subsystem Architecture & Schema — TARA

**Storage Engine:** SQLite 3 (Python standard library `sqlite3`)  
**Design Objective:** Zero-daemon, human-like non-destructive memory, persistent recall, low memory footprint (< 10MB RAM).  

---

## 1. Memory Philosophy & Tier Overview

TARA preserves history by default and avoids deleting user facts automatically:
1. **State Updates / Transitions:** When a singular state (like `current_project`) changes, the previous value is moved to `previous_project` with `status: 'archived'` rather than deleted.
2. **Additive Multi-Value Memory:** Preferences, skills, and likes are stored additively (e.g. liking Python and liking C++ coexist as active preferences).
3. **Identity Conflict Protection:** Singular identity keys (like `name`) are protected from accidental overwrites. Conflicting new values trigger a confirmation prompt to the user.

```
┌─────────────────────────────────────────────────────────────┐
│                    TARA Context Window                      │
├─────────────────────────────────────────────────────────────┤
│ 1. Core Persona & Instructions (~300 tokens)               │
│ 2. Structured User Context (~200 tokens)                   │
│    - Identity: Name (active)                                │
│    - Current Project (active) & Previous Projects (archived)│
│    - Multi-value Preferences (Python, C++, VS Code)         │
│ 3. Short-Term History Window (Last 6-10 turns, ~1500 tokens)│
│ 4. Current User Query + Response Window                     │
└─────────────────────────────────────────────────────────────┘
                             ▲
                             │ Dynamic Injection
┌─────────────────────────────────────────────────────────────┐
│              Persistent SQLite Database (tara.db)           │
├─────────────────────────────────────────────────────────────┤
│ • messages        (Historical chat transcripts)             │
│ • user_facts      (Non-destructive multi-value & archived)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema Definition

```sql
-- 1. Messages Table: Full sequential chat transcripts
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast sliding-window message queries
CREATE INDEX IF NOT EXISTS idx_messages_session_time 
ON messages(session_id, timestamp);

-- 2. User Facts Table: Non-destructive human-like memory store
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- 'identity', 'project', 'preference', 'goal', 'general'
    key TEXT NOT NULL,               -- 'name', 'current_project', 'previous_project', 'like', etc.
    value TEXT NOT NULL,             -- 'Raj', 'TARA', 'Rose', 'Python', 'C++'
    status TEXT DEFAULT 'active',    -- 'active', 'archived', 'pending_confirmation'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Python API Interface (`tara/memory.py`)

```python
class MemoryStore:
    def __init__(self, db_path: Optional[Path] = None): ...

    # Conversation History
    def save_message(self, session_id: str, role: str, content: str) -> None: ...
    def get_recent_messages(self, session_id: str, limit: int = 10) -> list[dict[str, str]]: ...

    # Safe Memory Operations
    def save_fact_safe(self, category: str, key: str, value: str) -> dict[str, Any]: ...
    def confirm_update_fact(self, category: str, key: str, new_value: str) -> None: ...
    def get_all_facts(self) -> dict[str, Any]: ...
    def extract_and_save_facts(self, text: str) -> list[dict[str, Any]]: ...
```

---

## 4. Example Lifecycle States

### State Transition (Projects)
- User: *"My current project is TARA"* $\rightarrow$ `(category: 'project', key: 'current_project', value: 'TARA', status: 'active')`
- User: *"My current project is Rose"* $\rightarrow$
  - Old Row updated: `(key: 'previous_project', status: 'archived')`
  - New Row inserted: `(category: 'project', key: 'current_project', value: 'Rose', status: 'active')`

### Additive Preferences
- User: *"I like Python"* $\rightarrow$ Row 1: `(category: 'preference', key: 'like', value: 'Python', status: 'active')`
- User: *"I like C++"* $\rightarrow$ Row 2: `(category: 'preference', key: 'like', value: 'C++', status: 'active')`

### Conflict Protection (Identity)
- Existing Name: `Raj` (`active`)
- User: *"My name is Rahul"* $\rightarrow$ Conflict detected. TARA asks: *"I previously had your name as Raj. Should I update it to Rahul?"*
- User confirms: *"Yes update my name to Rahul"* $\rightarrow$ `Raj` archived, `Rahul` activated.
