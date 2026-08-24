import os
import sys
import time
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.config import config
from tara.memory import MemoryStore
from tara.documents import DocumentEngine
from tara.workspace import KnowledgeWorkspace
from tara.vision import VisionEngine, OllamaVisionProvider
from tara.tools import registry
from tara.orchestrator import TARAOrchestrator
from tara.persona import get_system_prompt


def run_full_regression():
    print("===========================================================")
    print("PHASE 6.9 TARA COMPREHENSIVE RELIABILITY REGRESSION SUITE")
    print("===========================================================")

    # 1. Text Conversation & Single Request Flow Test
    print("\n[Regression 1: Text Conversation & Clean API Flow]")
    orch = TARAOrchestrator(mode="text")
    reply = orch.process_turn("Hello TARA, respond with 'Systems operational.'")
    print("• Orchestrator Reply:", reply.strip())
    assert len(reply) > 0, "Conversation response must not be empty"
    print("• Text Conversation Test: PASSED")

    # 2. Tools Execution Test
    print("\n[Regression 2: System Tools Execution]")
    time_res = registry.execute("get_current_time", {})
    print("• Time Tool Result:", time_res)
    assert "current time" in time_res.lower() or ":" in time_res

    battery_res = registry.execute("get_battery_status", {})
    print("• Battery Tool Result:", battery_res)
    assert len(battery_res) > 0
    print("• System Tools Execution Test: PASSED")

    # 3. Vision Intelligence (Local Moondream) Test
    print("\n[Regression 3: Vision Intelligence & Screen Analysis]")
    vision_engine = VisionEngine(primary_provider=OllamaVisionProvider(default_model="moondream:latest"))
    from tara.screen_capture import ScreenCapture
    sc = ScreenCapture()
    cap_path = sc.capture_screen()
    try:
        assert cap_path is not None and os.path.exists(cap_path), "Screen capture must succeed"
        analysis = vision_engine.analyze_image(cap_path, question="Identify open terminal or editor.")
        print("• Local Moondream Analysis Preview:\n ", analysis.get("description", "")[:120], "...")
        assert "description" in analysis
        print("• Vision Intelligence Test: PASSED")
    finally:
        if cap_path:
            sc.cleanup(cap_path)

    # 4. Documents & Relative Path Resolution Test
    print("\n[Regression 4: Document Understanding & Relative Path Resolution]")
    doc_engine = DocumentEngine()
    # Test relative workspace path
    req_text = doc_engine.extract_text("requirements.txt", max_chars=500)
    print("• Extracted requirements.txt preview:\n ", req_text[:100], "...")
    assert "groq" in req_text or "pypdf" in req_text

    # Test missing file error message
    try:
        doc_engine.extract_text("non_existent_folder/missing_file.pdf")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        print("• Handled missing file cleanly:", e)
    print("• Document Understanding & Path Resolution: PASSED")

    # 5. Memory Safety & Contamination Isolation Test
    print("\n[Regression 5: Memory Safety, Identity Consistency & Zero Contamination]")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        mem = MemoryStore(db_path=test_db)

        # Confirm queries are NOT remembered
        assert mem.classify_importance("Summarize requirements.txt in my workspace") == "IGNORE"
        assert mem.classify_importance("What does calculate_efficiency in utils.py do?") == "IGNORE"
        assert mem.classify_importance("Look at my screen and check for errors") == "IGNORE"

        # Explicit user fact
        mem.extract_and_save_facts("My name is Raj")
        mem.extract_and_save_facts("My current project is TARA")
        mem.extract_and_save_facts("I prefer Python for backend services")

        facts = mem.get_all_facts()
        print("• Stored facts:", facts)
        assert facts["name"] == "Raj"
        assert facts["current_project"] == "TARA"
        assert any("Python" in p for p in facts["preferences"])

        # Verify system prompt has confirmed identity override
        prompt = get_system_prompt(facts)
        assert "Raj" in prompt and "Confirmed identity" in prompt

        # Verify SQLite has no raw documents or binaries
        with mem._get_connection() as conn:
            rows = conn.execute("SELECT value FROM user_facts").fetchall()
            for r in rows:
                assert len(r["value"]) < 500, "user_facts must remain compact"

        print("• Memory Safety & Identity Consistency: PASSED")

    # 6. Fallback Mode Test
    print("\n[Regression 6: Fallback Mode & Local Offline Resilience]")
    # Verify Ollama fallback streams when invoked directly
    ollama_tokens = list(orch.llm._stream_ollama([{"role": "user", "content": "Respond with 'Fallback OK'" }]))
    ollama_reply = "".join(ollama_tokens).strip()
    print("• Ollama Fallback Output:", ollama_reply[:100])
    assert len(ollama_reply) > 0, "Ollama fallback must return a response"
    print("• Fallback Mode Test: PASSED")

    # 7. Performance & Resource Benchmark
    print("\n[Regression 7: Performance & RAM Footprint]")
    ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    print(f"• Total Process Peak RSS: {ram_mb:.2f} MB (Target: < 250 MB)")
    assert ram_mb < 250.0, "Total memory footprint must remain under 250MB"
    print("• Resource Benchmark: PASSED")

    print("\n===========================================================")
    print("PHASE 6.9 RELIABILITY REGRESSION SUITE: 100% PASSING!")
    print("===========================================================")


if __name__ == "__main__":
    run_full_regression()
