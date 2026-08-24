# Design & Interface Specifications — TARA

---

## 1. Persona & Tone Guidelines

TARA (**T**ransformative **A**I **R**easoning **A**rchitecture) is designed with the persona of a hyper-competent, calm, slightly witty, and utterly dependable technical co-pilot.

### 1.1 Voice Characteristics
- **Demeanor:** Professional, crisp, articulate, calm under pressure.
- **Language Style:** Concise and high-density. Avoids filler ("Certainly! I'd be delighted to assist you with...").
- **Voice Response Constraint:** Voice answers should be $\le$ 3 sentences whenever possible. Extensive data (code, lists, tabular data) is summarized via voice while printed in full to the terminal.

### 1.2 Example Voice Dialogues

> **User:** "TARA, what's my battery level and what time is it in San Francisco?"  
> **TARA (Voice):** "Battery is at 84% and discharging. It's 10:45 PM in San Francisco, Sir."  
> **TARA (CLI):** `[Tool: get_battery_status → 84%] [Tool: get_time_date → 22:45 PDT]`

> **User:** "Remember that my preferred language for backend projects is Go."  
> **TARA (Voice):** "Got it. I've noted that you prefer Go for backend development."  
> **TARA (CLI):** `[Memory Saved: user_backend_preference = Go]`

---

## 2. CLI & Terminal UI Design

Even when operating via voice, TARA provides rich, clean visual feedback in the terminal using standard ANSI formatting or rich formatting.

### 2.1 Visual Layout & State Indicators

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ TARA :: Transformative AI Reasoning Architecture v0.1.0  │
│  🧠 Brain: Groq (Llama-3.3-70B)  |  💾 Memory: Active (42 facts)│
│  🎙️ Ear: Faster-Whisper (base.en) |  🔊 Voice: Piper (Lessac) │
└─────────────────────────────────────────────────────────────┘

[Ready] Press SPACE to talk (or type command)...

[🎙️ Listening...] 
[⚙️ Transcribing...] "Search for latest developments in Apple Silicon M4"
[🧠 Thinking...]
  └─ [🔧 Tool Call: search_web(query='Apple Silicon M4 latest updates')]
  └─ [✅ Tool Complete: 4 results retrieved (320ms)]
[🔊 Speaking...]

TARA: Apple has announced the M4 chip lineup featuring enhanced neural accelerators and unified memory bandwidth up to 120 GB/s. I have displayed the detailed spec breakdown below.

---------------------------------------------------------------
* M4 Base: 10-core CPU, 10-core GPU, 38 TOPS NPU
* M4 Pro: Up to 14-core CPU, 20-core GPU
* Key Highlights: 28% faster CPU single-core performance over M3.
---------------------------------------------------------------
```

### 2.2 Status States
- `[Ready]`: Idle, waiting for voice trigger or keyboard input.
- `[🎙️ Listening...]`: Microphone actively recording audio stream.
- `[⚙️ Transcribing...]`: Audio chunk being processed by Faster-Whisper.
- `[🧠 Thinking...]`: LLM inference in progress.
- `[🔧 Executing <tool_name>...]`: Tool / API execution running.
- `[🔊 Speaking...]`: Piper / `say` generating audio output.

---

## 3. Tool Calling Protocol & Schema Design

TARA uses the standard OpenAI-compatible function calling specification, ensuring zero friction across both Groq API and Ollama:

```json
{
  "name": "execute_system_command",
  "description": "Execute a safe macOS system action such as volume control or app launching.",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["set_volume", "get_battery", "launch_app", "get_time"],
        "description": "The specific system action to perform."
      },
      "parameter": {
        "type": "string",
        "description": "Optional parameter, e.g. volume level (0-100) or application name."
      }
    },
    "required": ["action"]
  }
}
```

### 3.1 Tool Registration Pattern (Code-level Design)
```python
# Clean decorator-based registration: No boilerplate
@tool_registry.register(
    name="get_battery_status",
    description="Returns the current battery percentage and charging state."
)
def get_battery_status() -> str:
    # 5 lines of clean subprocess logic
    ...
```

---

## 4. Audio Pipeline Specifications

- **Sample Rate:** 16,000 Hz (16 kHz, 16-bit Mono PCM).
- **VAD Sensitivity:** Speech threshold energy calculation with 500ms trailing silence cutoff.
- **Audio Capture Buffer:** Rolling circular buffer in NumPy array format for low-memory allocation.
- **TTS Synthesis Format:** 22,050 Hz WAV output streamed directly to audio sink (`sounddevice` / `subprocess`).
- **Interruption Support:** Instant cancellation of TTS playback if user initiates a new speech cycle or taps ESC.

---

## 5. Graceful Degradation & Error Handling UX

| Failure Mode | Degraded Behavior | User Experience |
| :--- | :--- | :--- |
| **No Internet / Groq API down** | Auto-switches to local Ollama | Notice printed in CLI; TARA operates locally without interruption. |
| **Microphone unavailable / denied** | Fallback to interactive CLI text mode | Informs user via terminal and opens prompt input. |
| **Piper TTS unavailable** | Fallback to native macOS `say` | Audio continues seamlessly with system voice (`Samantha` or `Alex`). |
| **Tool Execution Error** | Tool returns clean error message to LLM | LLM explains the issue gracefully (e.g., "I couldn't locate that application, Sir."). |
