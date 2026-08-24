import enum
import time
import datetime
import logging
from typing import Optional
from tara.config import config
from tara.memory import MemoryStore
from tara.persona import get_system_prompt
from tara.llm import LLMClient
from tara.tools import registry
from tara.audio import TTSEngine, STTEngine
from tara.proactive import ProactiveEngine
from tara.emotion import EmotionEngine

logger = logging.getLogger("tara.orchestrator")


class State(enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    SPEAKING = "SPEAKING"


class TARAOrchestrator:
    """Central orchestrator managing lifecycle, state transitions, interaction loops, and emotional intelligence."""

    def __init__(self, mode: str = "text", voice_output: bool = False, session_id: Optional[str] = None):
        self.mode = mode
        self.voice_output = voice_output or (mode in ("voice", "wake"))
        self.state = State.IDLE
        self.session_id = session_id or f"session_{int(time.time())}"

        # Initialize subsystems
        self.memory = MemoryStore()
        self.llm = LLMClient()
        self.tts = TTSEngine()
        self.stt = STTEngine(model_size="tiny.en")
        self.tool_schemas = registry.get_schemas()
        self._wake_detector = None
        self.proactive = ProactiveEngine(orchestrator=self)
        self.emotion_engine = EmotionEngine()

    def set_state(self, state: State, detail: str = "") -> None:
        """Update orchestrator state and log transition."""
        self.state = state
        if detail:
            print(f"[{state.value}] {detail}")
        logger.debug(f"State transition: {state.value} {detail}")

    def get_greeting(self) -> str:
        """Generate time-appropriate greeting with user's name if known in memory."""
        hour = datetime.datetime.now().hour
        time_greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        facts = self.memory.get_all_facts()
        name = facts.get("name", "Sir")
        return f"{time_greeting} {name}. Systems online."

    def _compact_episodic_memory(self) -> None:
        """Incrementally summarize older turns when unsummarized threshold is met."""
        try:
            unsummarized, max_id, existing_summary = self.memory.get_unsummarized_messages(self.session_id, keep_recent=6)
            if len(unsummarized) >= 4:
                transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in unsummarized)
                if existing_summary:
                    prompt_text = (
                        "You are updating an episodic conversation summary. Consolidate the previous summary with the new dialogue turns into a compact, bulleted summary (3-5 lines). "
                        "CRITICAL: Retain all previously established technical decisions, progress, and pending tasks from the previous summary while integrating new milestones. "
                        "Strictly exclude temporary feelings, weather remarks, and trivial conversational chatter.\n\n"
                        f"[Previous Summary]:\n{existing_summary}\n\n[New Dialogue Turns]:\n{transcript}"
                    )
                else:
                    prompt_text = (
                        "Summarize the key technical decisions, completed work, unresolved tasks, and important context from this dialogue into a compact, bulleted summary (2-4 lines). "
                        "Strictly exclude temporary feelings, weather remarks, and trivial greetings.\n\n"
                        f"[Dialogue Turns]:\n{transcript}"
                    )

                summary_prompt = [
                    {"role": "system", "content": "You are a concise technical summarizer. Return only the bulleted summary."},
                    {"role": "user", "content": prompt_text}
                ]
                new_summary = self.llm.generate(summary_prompt)
                if new_summary and not new_summary.startswith("I am unable to reach"):
                    self.memory.save_episodic_summary(self.session_id, new_summary, max_id)
        except Exception as e:
            logger.warning(f"Episodic memory compaction failed gracefully: {e}")

    def process_turn(self, user_input: str, stream_display: bool = True) -> str:
        """Execute a full conversational turn with emotional awareness, streaming output, and sentence-by-sentence TTS."""
        if not user_input or not user_input.strip():
            return ""

        clean_input = user_input.strip()

        # 1. Emotional Context Analysis
        emotion_result = self.emotion_engine.analyze(clean_input)
        self.memory.save_conversation_emotion(
            self.session_id,
            emotion_result["emotion"],
            emotion_result["confidence"]
        )

        # 2. Fact extraction & conflict detection
        fact_results = self.memory.extract_and_save_facts(clean_input)
        conflict_msg = next((r["message"] for r in fact_results if r.get("action") == "conflict"), None)

        if conflict_msg:
            reply = conflict_msg
            if stream_display:
                print(f"\nTARA: {reply}\n")
            if self.voice_output:
                self.tts.speak(reply)
        else:
            self.set_state(State.THINKING)
            # 3. Context Assembly: Persona + Facts + Emotional Guidance + Episodic Summary + Recent Messages + Current Message
            facts = self.memory.get_all_facts()
            system_prompt = get_system_prompt(facts, emotion_state=emotion_result)
            episodic_summary = self.memory.get_episodic_summary(self.session_id)
            recent_messages = self.memory.get_recent_messages(self.session_id, limit=6)

            messages = [{"role": "system", "content": system_prompt}]
            if episodic_summary:
                messages.append({
                    "role": "system",
                    "content": f"[Episodic Summary of Earlier Turns in this Session]:\n{episodic_summary}"
                })
            messages.extend(recent_messages)
            messages.append({"role": "user", "content": clean_input})

            # 4. LLM streaming reasoning and tool resolution
            token_stream = self.llm.generate_stream(messages, tools=self.tool_schemas)

            if stream_display:
                print("\nTARA: ", end="", flush=True)

            def print_chunk(chunk: str):
                if stream_display:
                    print(chunk, end="", flush=True)

            if self.voice_output:
                self.set_state(State.SPEAKING)
                reply = self.tts.speak_stream(token_stream, on_chunk=print_chunk)
            else:
                chunks = []
                for chunk in token_stream:
                    chunks.append(chunk)
                    print_chunk(chunk)
                reply = "".join(chunks)

            if stream_display:
                print("\n")

        # 5. Commit turn to SQLite memory
        self.memory.save_message(self.session_id, "user", clean_input)
        self.memory.save_message(self.session_id, "assistant", reply)

        # 6. Check and perform incremental episodic compaction
        self._compact_episodic_memory()

        self.set_state(State.IDLE)
        return reply

    def run(self) -> None:
        """Run the interactive orchestration loop with proactive background awareness."""
        print("=" * 65)
        print("  ⚡ TARA :: Transformative AI Reasoning Architecture v0.1.0")
        print(f"  🧠 Brain: {config.default_provider.upper()} ({config.groq_model if config.default_provider == 'groq' else config.ollama_model})")
        print(f"  💾 Memory: {config.db_path}")
        print(f"  🎙️ Ear: Faster-Whisper (tiny.en) | 🔊 Voice: {self.tts.voice} ({'Active' if self.voice_output else 'Off'})")
        print(f"  🕹️ Mode: {self.mode.upper()} (Type ':mode' to cycle modes, 'exit' to quit)")
        print("=" * 65)

        # Startup greeting
        greeting = self.get_greeting()
        print(f"\nTARA: {greeting}\n")
        if self.voice_output:
            self.tts.speak(greeting)

        # Start proactive scheduler thread
        self.proactive.start()

        try:
            if self.mode == "wake":
                from tara.wakeword import WakeWordDetector
                self._wake_detector = WakeWordDetector(threshold=0.5)
                print("[⚡ Wake Word Active] Say 'Hey TARA' / 'Hey Jarvis' to activate, or press Ctrl+C to quit.\n")

                while True:
                    try:
                        self.set_state(State.IDLE, "Standby (Listening for 'Hey TARA')...")
                        detected = self._wake_detector.listen_for_wake()
                        if not detected:
                            break

                        print("\n⚡ [Wake Word Detected!]")
                        self.set_state(State.LISTENING, "Listening for command (auto-stops on silence)...")
                        audio_data = self.stt.record_audio()
                        if audio_data is not None:
                            self.set_state(State.THINKING, "Transcribing speech...")
                            user_input = self.stt.transcribe(audio_data)
                            if user_input:
                                print(f"You (Voice): {user_input}")
                                _ = self.process_turn(user_input, stream_display=True)
                            else:
                                print("[🎙️ No speech detected. Returning to standby.]\n")
                        else:
                            print("[🎙️ Microphone unavailable. Returning to standby.]\n")
                    except (KeyboardInterrupt, EOFError):
                        print("\nTARA: Session terminated.")
                        break
                    except Exception as e:
                        print(f"\n[Error]: {e}\n")
                        self.set_state(State.IDLE)
                return

            if self.mode == "voice":
                print("[Voice Mode Active] Press ENTER to speak (auto-stops on silence), or type directly.\n")

            while True:
                try:
                    if self.mode == "voice":
                        user_raw = input("You (Press ENTER to speak or type text): ").strip()
                        if not user_raw:
                            self.set_state(State.LISTENING, "Listening (auto-detects silence)...")
                            audio_data = self.stt.record_audio()
                            if audio_data is not None:
                                self.set_state(State.THINKING, "Transcribing speech...")
                                user_input = self.stt.transcribe(audio_data)
                                if not user_input:
                                    print("[🎙️ No speech detected. Please speak clearly or press ENTER to try again.]\n")
                                    self.set_state(State.IDLE)
                                    continue
                                print(f"You (Voice): {user_input}")
                            else:
                                print("[🎙️ Microphone unavailable or permission denied. Please type your message below.]\n")
                                self.set_state(State.IDLE)
                                continue
                        else:
                            user_input = user_raw
                    else:
                        user_input = input("You: ").strip()
                        if not user_input:
                            continue

                    # Command check
                    if user_input.lower() in ("exit", "quit", "q"):
                        farewell = "Shutting down. Have a productive day."
                        print(f"\nTARA: {farewell}")
                        if self.voice_output:
                            self.tts.speak(farewell)
                        break

                    if user_input.lower() == ":mode":
                        modes = ["text", "voice", "wake"]
                        idx = (modes.index(self.mode) + 1) % len(modes)
                        self.mode = modes[idx]
                        self.voice_output = (self.mode in ("voice", "wake"))
                        print(f"\n[Switched to {self.mode.upper()} mode (Voice output: {'Enabled' if self.voice_output else 'Disabled'})]\n")
                        if self.mode == "wake":
                            return self.run()
                        continue

                    _ = self.process_turn(user_input, stream_display=True)

                except (KeyboardInterrupt, EOFError):
                    print("\nTARA: Session terminated.")
                    break
                except Exception as e:
                    print(f"\n[Error]: {e}\n")
                    self.set_state(State.IDLE)

        finally:
            self.proactive.stop()
