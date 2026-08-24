# Engineering Rules & Guidelines — TARA

**Guiding Axiom:** Simple, robust, maintainable code beats complex, clever architecture every time. Build TARA like a real product that can grow, not like an enterprise demo bloated with unused abstractions.

---

## 1. Core Engineering Principles

1. **No Over-Engineering:**
   - Do not write code to make the project look big or complex.
   - If a feature can be cleanly implemented in 20 lines, do not expand it to 200 lines.
   - Avoid creating multiple layers of abstract base classes and factories unless there are at least three distinct, active implementations that justify it.
   - Every file, class, function, and dependency must serve an immediate, measurable purpose.

2. **Lean Dependencies:**
   - Prefer standard library modules (`sqlite3`, `subprocess`, `urllib.request`, `json`, `dataclasses`, `pathlib`, `logging`, `typing`) over heavy external packages.
   - Do not install heavy vector databases (ChromaDB, Pinecone, Milvus) for local-first single-user memory. Use SQLite + FTS5.
   - Do not use bloated LLM orchestration frameworks (LangChain, LlamaIndex, CrewAI) when direct API client calls provide 10x better transparency, speed, and reliability.

3. **MacBook Air M1 (8GB RAM) Budget Compliance:**
   - Total idle memory footprint must remain under 100 MB.
   - Total active processing memory footprint must stay under 1.5 GB.
   - Never load large multi-gigabyte models into memory simultaneously.
   - Ensure native ARM64 / Metal compatibility for all binary dependencies.

---

## 2. Code Quality & Standards

### 2.1 Python Conventions
- **Target Version:** Python 3.10+.
- **Type Annotations:** Use standard Python type hinting (`list[str]`, `dict[str, Any]`, `Optional[int]`) on all public function signatures.
- **Data Containers:** Use `@dataclass` or TypedDict for structured data transfer; avoid ad-hoc unstructured dictionaries where types matter.
- **Async vs Sync:** Keep the core pipeline synchronous and straightforward for MVP. Use threading or lightweight `asyncio` strictly where non-blocking I/O is necessary (e.g., streaming audio playback while generating text).
- **Docstrings & Comments:** Comment only *why* non-obvious logic exists, not *what* self-explanatory code does. Do not clutter code with redundant comments.

### 2.2 Error Handling & Resilience
- Every external call (Groq API, Ollama daemon, macOS subprocess, Web search, Audio stream) must have explicit `try...except` handling with meaningful fallback behavior.
- The assistant must **never crash** on user input or API failure. If Groq is unreachable, fall back to Ollama or voice an informative error.
- Never write bare `except:`; catch specific exceptions (`requests.RequestException`, `subprocess.CalledProcessError`, `sqlite3.Error`).

### 2.3 Logging & Observability
- Use standard Python `logging` with structured formatting:
  - `DEBUG`: Raw token streams, tool JSON payloads, audio capture metrics.
  - `INFO`: User query transcript, tool execution status, latency metrics.
  - `WARNING` / `ERROR`: Fallback triggers, API failures, tool execution errors.
- Never use stray `print()` statements inside library modules (`brain/`, `audio/`, `memory/`, `tools/`). Only `main.py` / CLI renderers may print to stdout.

---

## 3. System Execution & Safety Rules

TARA has access to system tools and commands. To guarantee system safety:

1. **Whitelisted Execution:** System tools must only execute safe, explicit operations (e.g., adjust volume, launch applications, check battery, retrieve system time, run read-only scripts).
2. **Never Execute Arbitrary Destructive Commands:** Disallow unvalidated commands such as `rm -rf`, disk partitioning, modification of system root files, or downloading and executing untrusted shell scripts.
3. **User Confirmation for Critical Actions:** Any high-impact action (file deletion, sending emails, terminating critical processes) requires explicit user confirmation.

---

## 4. TARA Persona & Behavioral Rules

1. **Tone & Demeanor:**
   - Professional, intelligent, articulate, slightly witty, and deeply efficient (inspired by FRIDAY/JARVIS).
   - Address the user respectfully (e.g., "Sir", "Boss", or by name if set in memory).
2. **Conciseness in Voice Output:**
   - When responding via voice (TTS), keep responses concise, conversational, and direct (1–3 sentences) unless an in-depth explanation is explicitly requested.
   - Avoid reading out raw URLs, markdown tables, or code blocks over voice; instead summarize them and display details in the terminal.
3. **Tool Calling Transparency:**
   - Acknowledge tool actions smoothly (e.g., "Checking your calendar now...", "Searching for the latest news on...").
   - When tool results are available, synthesize them into a coherent answer rather than dumping raw JSON.
4. **Memory Respect:**
   - Proactively remember user preferences and facts when instructed ("Remember that my favorite editor is VS Code").
   - Never overwrite user facts without confirmation.
