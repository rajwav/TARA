# Product Requirements Document (PRD) — TARA

**Project Name:** TARA (Transformative AI Reasoning Architecture)  
**Target Platform:** macOS (MacBook Air M1, 8GB RAM)  
**Implementation Language:** Python 3.10+  
**Architecture Style:** Local-First, Modular, Resource-Constrained, Anti-Overengineering  
**Status:** Approved for Documentation / Pre-Implementation  

---

## 1. Executive Summary & Vision

TARA is a lightweight, responsive, personal AI assistant designed to run efficiently on an Apple Silicon MacBook Air (M1, 8GB RAM). Inspired by sci-fi AI interfaces (JARVIS / FRIDAY), TARA is **not** a generic chatbot. It is a proactive, voice-capable, tool-wielding, reasoning companion with persistent memory, system control capabilities, and a distinct personality.

### Core Value Proposition
- **High Responsiveness & Low Memory Footprint:** Operates within a strict 8GB RAM budget without choking the OS.
- **Hybrid Intelligence:** Seamlessly switchable between ultra-fast cloud inference (Groq API) for instant voice interaction and private local inference (Ollama - Llama 3.2 / Qwen 2.5) when offline.
- **Voice-First Capability:** Fast Speech-to-Text (Faster-Whisper / Whisper.cpp) and natural, low-latency Text-to-Speech (Piper TTS / macOS `say` fallback).
- **Action-Oriented (Tools):** Native execution of macOS system commands, calendar/time checks, web search, and RSS fetching.
- **Episodic & Semantic Memory:** SQLite-based conversation history and contextual knowledge retention without bloated vector database daemons.

---

## 2. Target Users & Operating Constraints

### User Persona
- **Primary User:** A developer / power user on macOS requiring an autonomous assistant for system control, quick information retrieval, task reasoning, and hands-free voice interaction.

### Hardware & Software Constraints
| Parameter | Constraint | Rationale / Mitigation |
| :--- | :--- | :--- |
| **RAM Budget** | $\le$ 1.5 GB Total for TARA | System has 8GB shared unified memory; leaving >6.5GB for user apps. |
| **Processor** | Apple M1 (8-core CPU, Metal GPU/ANE) | Use ARM64-optimized runtimes (`faster-whisper`, CoreML/Metal where applicable). |
| **Storage Footprint** | $\le$ 2 GB (including models & voices) | Use lightweight Whisper models (tiny/base) and compact Piper ONNX voices (medium quality, ~50MB). |
| **Latency Target** | < 1.0s voice response (cloud) / < 2.5s (local) | Crucial for conversational flow. |

---

## 3. Key Feature Requirements

### 3.1 Voice & Audio Subsystem (Ear & Voice)
- **STT (Speech-to-Text):**
  - Continuous or push-to-talk audio capture using PyAudio / SoundDevice.
  - Efficient transcription via `faster-whisper` (`tiny.en` or `base.en`).
  - Voice Activity Detection (VAD) using Silero-VAD or simple energy thresholding to prevent transcription of dead silence.
- **TTS (Text-to-Speech):**
  - High-speed, natural offline voice generation via Piper TTS (ONNX).
  - Native macOS `say` utility fallback for zero-dependency operation.
  - Non-blocking audio playback with interruptibility.

### 3.2 Cognitive & Reasoning Engine (Brain)
- **Hybrid LLM Provider:**
  - **Primary (High Speed):** Groq API (Llama 3.3 70B / Llama 3.1 8B) for ~300–500 tokens/sec streaming response.
  - **Secondary (Offline / Local):** Ollama (Llama 3.2 1B/3B or Qwen 2.5 1.5B/3B quantized 4-bit) for 100% private offline reasoning.
- **Persona & Prompting:**
  - Concise, articulate, professional yet witty demeanor (inspired by FRIDAY/JARVIS).
  - Built-in system prompt maintaining character consistency and tool-calling discipline.
- **Structured Tool Execution:**
  - Tool/Function calling schema allowing the model to request external actions before answering.

### 3.3 Memory & Context Management (Recall)
- **Short-Term Context:** Sliding-window conversation buffer with automatic token management.
- **Long-Term Memory:** Zero-daemon SQLite database storing:
  - Timestamped chat history.
  - Key-value user preferences & extracted facts (e.g., user name, favorite apps, reminders).
  - Fast full-text search via SQLite FTS5 (Zero heavy vector DB overhead).

### 3.4 Tool & Action Execution (Hands)
- **System Tools:** Current time/date, macOS volume/brightness control, app launcher (via AppleScript / `open`), battery status.
- **Information Tools:** DuckDuckGo Web Search, RSS Feed Reader / Tech news digest.
- **Extensible Tool Registry:** Clean decorator-based or class-based registry allowing additions in < 15 lines of code.

---

## 4. MVP (Minimum Viable Product) Scope — Target: 6 Hours

The MVP must be fully functional end-to-end within 6 hours, prioritizing working capability over extraneous bells and whistles.

### MVP Features (Included):
1. **Interactive CLI & Voice Loop:** Text mode and Push-to-Talk voice mode.
2. **Dual-Brain LLM Engine:** Groq API client with fallback/switch to local Ollama.
3. **Core STT & TTS:** Faster-Whisper (base.en) + Piper TTS / macOS `say`.
4. **SQLite Memory Store:** Schema for sessions, messages, and key-value user facts.
5. **Initial 4 Tools:**
   - `get_current_time_date`
   - `execute_system_command` (macOS control: volume, launch app, battery)
   - `web_search` (DuckDuckGo search)
   - `manage_memory` (store/retrieve explicit user facts)
6. **Unified Orchestrator:** The loop that routes speech $\rightarrow$ text $\rightarrow$ memory $\rightarrow$ reasoning $\rightarrow$ tool execution $\rightarrow$ voice response.

### Non-MVP Features (Deferred to Post-MVP):
- GUI / HUD visual interface.
- Custom wake-word engine (e.g., OpenWakeWord / Porcupine).
- Screen capture / multimodal vision analysis.
- Complex autonomous multi-agent task planning.

---

## 5. Success Metrics

1. **End-to-End Latency:** Time from end of user speech to start of voice response < 1.5 seconds on Groq, < 3.5 seconds on local Ollama.
2. **RAM Stability:** Peak RAM usage under 1.2 GB during active audio + inference.
3. **Execution Reliability:** 95%+ success rate on tool call parsing and system action execution.
4. **Code Quality:** Zero boilerplate dead code, zero unused dependencies, strictly clean Python codebase.
