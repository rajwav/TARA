# TARA :: Transformative AI Reasoning Architecture

**TARA** is a fast, lightweight, privacy-first personal AI assistant engineered in Python and optimized for Apple Silicon (macOS M1/M2/M3). Inspired by JARVIS-style co-pilot interfaces, TARA combines single-request LLM streaming, deterministic SQLite memory, autonomous system action control, document analysis, and hands-free voice interaction without heavy frameworks, vector databases, or LangChain bloat.

---

## Key Capabilities

- **Hybrid Cloud/Local Brain**: Ultra-fast cloud reasoning via Groq (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) with seamless local fallback to Ollama (`llama3.2:3b`).
- **Human-Like SQLite Memory**: Non-destructive user fact extraction, automatic project archiving, conflict detection, and incremental episodic conversation summary compaction.
- **Safe macOS Action Execution**:
  - System monitoring: CPU load, unified RAM metrics, disk storage, active GUI application listing, and battery telemetry.
  - Safe file management: directory listing, file/folder creation, and moving with permission checks.
  - macOS application control: open apps (VS Code, Calculator, Safari, Finder, Terminal) and project folders.
  - Browser actions: DuckDuckGo search integration and web URL opener.
- **Audited Security Model**: Enforces `LOW`, `MEDIUM`, and `HIGH` risk tiers, prevents path traversal, blocks system root modifications (`/System`, `/Library`, `/usr`), and logs every action to an SQLite audit table.
- **Document & Source Code Intelligence**: Extracts and summarizes PDF, Markdown, TXT, JSON, YAML, and 20+ code file extensions via `pypdf` without permanently retaining raw file bodies.
- **Vision Intelligence (On-Demand)**: Private screen capture analysis via local Ollama `moondream:latest` with zero persistent image storage.
- **Audio & Wake Word Pipeline**:
  - Voice Activity Detection (VAD) audio recording via `sounddevice` and `numpy`.
  - Fast Speech-to-Text via `faster-whisper` (`tiny.en` int8 on CPU).
  - Streaming sentence-by-sentence Text-to-Speech via macOS `say`.
  - Hands-free wake word detection via `openWakeWord` ("Hey TARA" / "Hey Jarvis").

---

## Architecture

```
                                  [ User Input ]
                         (Text CLI / Voice / Wake Word)
                                       │
                                       ▼
                       [ TARA Orchestrator & Persona ]
                 (Dynamic System Prompt + SQLite Memory Context)
                                       │
                                       ▼
                             [ Unified LLM Engine ]
                        ├── Primary: Groq API (Cloud)
                        └── Fallback: Ollama (Local)
                                       │
                                       ▼
                             [ Autonomous Tools ]
          ┌─────────────────┬──────────────────┬─────────────────┐
          ▼                 ▼                  ▼                 ▼
   [ Action Layer ]   [ Documents ]     [ Vision Engine ]  [ Audio / TTS ]
   - App Launcher     - PDF / Code      - Ollama Moondream - Faster-Whisper
   - System Metrics   - Summarizer      - Screen Capture   - macOS 'say'
   - File Operations
          │
          ▼
   [ SecurityGuard ] (Risk Tiers + SQLite Action Audit Log)
```

---

## Platform Requirements

- **Operating System**: macOS (Darwin) recommended for full system actions, screen capture, and native speech synthesis.
- **Python**: Python 3.10 - 3.14
- **Local Vision/LLM (Optional)**: [Ollama](https://ollama.com) (`ollama run moondream:latest` and `ollama run llama3.2:3b`)

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rajwav/TARA.git
   cd TARA
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Groq API key (free at [console.groq.com](https://console.groq.com)):
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=openai/gpt-oss-120b
   DEFAULT_LLM_PROVIDER=groq
   DATABASE_PATH=data/tara.db
   LOG_LEVEL=INFO
   ```

---

## Usage

### 1. Text Mode (Default)
Run interactive CLI chat with streaming responses and full tool capabilities:
```bash
python main.py --mode text
```

### 2. Voice Mode
Push-to-talk interactive mode with automated speech recognition and voice playback:
```bash
python main.py --mode voice
```

### 3. Wake Word Mode
Hands-free continuous listener activated by saying *"Hey Jarvis"* or *"Hey TARA"*:
```bash
python main.py --mode wake
```

---

## Running Automated Tests

Run the complete regression test suite:
```bash
# Core stabilization & tool execution test
python tests/test_stabilization.py

# Safe action execution & security boundary test
python tests/test_actions.py

# Document intelligence & PDF extraction test
python tests/test_documents.py

# Memory & reliability regression test
python tests/test_regression.py

# Personal knowledge workspace test
python tests/test_workspace.py
```

---

## Security & Privacy Model

- **No Data Exfiltration**: User memory and personal facts stay strictly in your local SQLite database (`data/tara.db`).
- **Temporary Vision & Document Isolation**: Screenshots and raw document text are held in memory during analysis and immediately purged.
- **Protected File Paths**: Root system directories (`/`, `/System`, `/Library`, `/usr`, `/etc`) are hard-blocked from write and modification operations.
- **Audit Logging**: Every action executed by TARA records its timestamp, risk level, arguments, and status into the `action_history` table.

---

## License

This project is licensed under the [MIT License](LICENSE).
