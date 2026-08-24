# Implementation Roadmap & Phases — TARA

**Target:** 6-Hour Functional MVP on macOS (M1, 8GB RAM)  
**Execution Strategy:** Sequential, Test-Driven at Each Phase, Zero Premature Optimization  

---

## Roadmap Overview

```
Phase 0: Architecture & Setup (30 min)
   ↓
Phase 1: Core Brain & Memory (60 min)
   ↓
Phase 2: Tool Execution System (60 min)
   ↓
Phase 3: Audio Engine — STT & TTS (90 min)
   ↓
Phase 4: Full Pipeline Integration & Tuning (60 min)
   ↓
Phase 5: Post-MVP Enhancements (Future)
```

---

## Phase 0: Architecture & Environment Setup
**Estimated Time:** 30 Minutes  
**Goal:** Establish clean project workspace, documentation, virtual environment, and dependency configuration.

### Tasks
- [x] Create project documentation (`/docs/PRD.md`, `Architecture.md`, `Rules.md`, `Phases.md`, `Design.md`, `Memory.md`).
- [ ] Create `requirements.txt` with minimal, non-bloated dependencies.
- [ ] Create `.env.example` and config loader (`tara/config.py`).
- [ ] Verify Python 3.10+ virtual environment and ARM64 packages.

### Deliverables
- Working virtual environment.
- Config parser loading environment variables (`GROQ_API_KEY`, `OLLAMA_HOST`, etc.).

---

## Phase 1: Core Brain & Memory Subsystems
**Estimated Time:** 60 Minutes  
**Goal:** Build the LLM reasoning client (Groq + Ollama), persona system prompt, and SQLite conversation memory with CLI interaction.

### Tasks
- [ ] Implement `tara/memory/store.py`:
  - SQLite schema for `sessions`, `messages`, and `user_facts`.
  - Methods: `add_message`, `get_recent_history`, `set_fact`, `get_fact`, `search_facts`.
- [ ] Implement `tara/brain/persona.py`:
  - System prompt definition with TARA personality, tool usage rules, and formatting directives.
- [ ] Implement `tara/brain/llm_client.py`:
  - Unified client supporting Groq API (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) with automatic fallback to Ollama (`llama3.2:3b` / `qwen2.5:3b`).
  - Native tool/function-calling payload formatting.
- [ ] Create basic interactive CLI test loop (`main.py --mode text`).

### Phase 1 Verification Criteria
- Run CLI text chat: TARA answers with persona, persists chat in SQLite, and correctly references past conversational context.

---

## Phase 2: Tool Execution System (The Hands)
**Estimated Time:** 60 Minutes  
**Goal:** Build a clean, lightweight tool registry and implement core tools for system control, web search, RSS news, and memory management.

### Tasks
- [ ] Implement `tara/tools/registry.py`:
  - `@tool` decorator pattern for easy function registration and auto-generation of JSON schema definitions for the LLM.
- [ ] Implement `tara/tools/system_tools.py`:
  - `get_system_time_date()`
  - `get_battery_status()`
  - `set_system_volume(level: int)`
  - `launch_application(app_name: str)`
- [ ] Implement `tara/tools/web_tools.py`:
  - `search_web(query: str, max_results: int = 4)` using DuckDuckGo search.
  - `get_tech_news(rss_url: Optional[str] = None)` for instant RSS feed summaries.
- [ ] Implement `tara/tools/memory_tools.py`:
  - `save_user_fact(key: str, value: str)`
  - `recall_user_facts(query: Optional[str] = None)`
- [ ] Connect Tool Registry to `tara/orchestrator.py` tool calling loop.

### Phase 2 Verification Criteria
- Prompting TARA with *"What time is it in Tokyo?"*, *"Turn volume to 50%"*, or *"Remember my name is Raj and I work on AI"* triggers proper tool execution and coherent responses.

---

## Phase 3: Audio Engine — STT & TTS (The Ear & Voice)
**Estimated Time:** 90 Minutes  
**Goal:** Implement low-latency offline speech recognition and natural voice synthesis.

### Tasks
- [ ] Implement `tara/audio/tts.py`:
  - Primary: Piper TTS (local ONNX neural voice).
  - Fallback: macOS native `say` utility (zero-install fallback).
  - Streaming/non-blocking audio output with interrupt handling.
- [ ] Implement `tara/audio/stt.py`:
  - Faster-Whisper wrapper loading `base.en` (or `tiny.en`).
  - Audio capture from microphone using `sounddevice` or `pyaudio`.
  - Energy/Silero-based VAD for automatic silence cutoff.
- [ ] Implement Push-to-Talk (Spacebar/Key press) and continuous listen loop.

### Phase 3 Verification Criteria
- Speak into microphone $\rightarrow$ accurate transcription generated in < 300ms $\rightarrow$ TARA speaks back naturally via Piper / `say`.

---

## Phase 4: Full Pipeline Integration & Tuning
**Estimated Time:** 60 Minutes  
**Goal:** Wire Audio + Brain + Memory + Tools into a cohesive, rock-solid assistant loop.

### Tasks
- [ ] Finalize `tara/orchestrator.py` multi-modal loop:
  - Input (Voice / CLI) $\rightarrow$ Memory injection $\rightarrow$ LLM reasoning $\rightarrow$ Tool resolution $\rightarrow$ Output (TTS + CLI display) $\rightarrow$ SQLite commit.
- [ ] Optimize latency on M1 Mac (model caching, connection keep-alive).
- [ ] Build robust error boundaries (graceful degraded mode when offline or on API timeout).
- [ ] Create `main.py` entrypoint with clean command-line flags (`--voice`, `--text`, `--local`, `--groq`).

### Phase 4 Verification Criteria
- Complete end-to-end voice conversation with tool execution within the latency budget (< 1.5s total turnaround).

---

## Phase 5: Post-MVP Extensions (Future Roadmap)
- [ ] Always-on wake-word engine ("Hey TARA").
- [ ] Minimalist GUI / Menu bar widget with animated audio visualizer.
- [ ] Vision / Screen analysis tool (take screenshot and reason about code/UI).
- [ ] Proactive background tasks (cron-like reminders, daily morning briefing).
