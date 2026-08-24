import sys
import time
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.emotion import EmotionEngine
from tara.memory import MemoryStore
from tara.persona import get_system_prompt
from tara.orchestrator import TARAOrchestrator


def run_tests():
    print("===========================================================")
    print("PHASE 6.4 EMOTIONAL INTELLIGENCE & ADAPTATION SUITE")
    print("===========================================================")

    engine = EmotionEngine()

    # Test 1: Excited
    res1 = engine.analyze("I finally completed my project")
    print(f"[Test 1: Excited] Input: 'I finally completed my project' -> Detected: {res1['emotion']} (Conf: {res1['confidence']})")
    assert res1["emotion"] == "excited", f"Expected excited, got {res1['emotion']}"

    # Test 2: Frustrated
    res2 = engine.analyze("This error is annoying and I am stuck")
    print(f"[Test 2: Frustrated] Input: 'This error is annoying and I am stuck' -> Detected: {res2['emotion']} (Conf: {res2['confidence']})")
    assert res2["emotion"] == "frustrated", f"Expected frustrated, got {res2['emotion']}"

    # Test 3: Tired
    res3 = engine.analyze("I am tired after coding")
    print(f"[Test 3: Tired] Input: 'I am tired after coding' -> Detected: {res3['emotion']} (Conf: {res3['confidence']})")
    assert res3["emotion"] == "tired", f"Expected tired, got {res3['emotion']}"

    # Test 4: Neutral
    res4 = engine.analyze("Explain transformers")
    print(f"[Test 4: Neutral] Input: 'Explain transformers' -> Detected: {res4['emotion']} (Conf: {res4['confidence']})")
    assert res4["emotion"] == "neutral", f"Expected neutral, got {res4['emotion']}"

    # Test 5: Temporary emotions do NOT enter user_facts
    print("\n[Test 5: Memory Isolation Check (No Emotion in user_facts)]")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        memory = MemoryStore(db_path=test_db)
        session_id = "test_session_emotion"

        # Simulate turns with emotional inputs
        memory.extract_and_save_facts("This bug is driving me crazy and I'm frustrated")
        memory.extract_and_save_facts("I am feeling tired today")
        memory.save_conversation_emotion(session_id, "frustrated", 0.9)

        facts = memory.get_all_facts()
        print("Facts in user_facts table:", facts)
        assert "frustrated" not in str(facts).lower(), "Emotions must not be stored in user_facts!"
        assert "tired" not in str(facts).lower(), "Emotions must not be stored in user_facts!"

        # Verify session state DOES have the emotion
        latest_emotion = memory.get_latest_emotion(session_id)
        print("Session conversation_state:", latest_emotion)
        assert latest_emotion is not None and latest_emotion["emotion"] == "frustrated"
        print("• Memory isolation verified: PASSED")

    # Test 6: Emotional Context reaches LLM Prompt
    print("\n[Test 6: Prompt Context Injection Check]")
    facts_mock = {"name": "Raj", "current_project": "TARA"}
    prompt = get_system_prompt(facts_mock, emotion_state=res2)
    print("Generated Prompt snippet:\n", "\n".join(prompt.split("\n")[-4:]))
    assert "[Emotional Context & Adaptive Response Style]" in prompt
    assert "frustrated" in prompt
    assert "patient" in prompt.lower()
    print("• Prompt injection verified: PASSED")

    # Test 7 & 8: Latency & RAM Footprint Benchmark
    print("\n[Test 7 & 8: Latency & RAM Resource Benchmark]")
    latencies = []
    for _ in range(1000):
        t0 = time.perf_counter()
        _ = engine.analyze("I finally finished building the feature and I'm super excited!")
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    print(f"• Average Emotion Analysis Latency: {avg_latency:.4f} ms (Target: < 10ms)")
    print(f"• Max Emotion Analysis Latency:     {max_latency:.4f} ms (Target: < 10ms)")
    print(f"• Peak Process Memory:              {ram_mb:.2f} MB (Target increase: < 5MB)")
    assert avg_latency < 10.0, "Latency must be under 10ms"

    # Test 9: Achievement Recognition
    print("\n[Test 9: Achievement Recognition Check]")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        mem = MemoryStore(db_path=test_db)

        # Meaningful achievement
        mem.extract_and_save_facts("I completed Phase 6.4 of TARA")
        mem.extract_and_save_facts("Finished building wake word system")

        # Trivial fix (should be ignored)
        mem.extract_and_save_facts("Fixed a typo in documentation")

        saved_facts = mem.get_all_facts()
        print("Recognized Achievements:", saved_facts["achievements"])
        assert any("Phase 6.4 of TARA" in a for a in saved_facts["achievements"])
        assert any("wake word system" in a for a in saved_facts["achievements"])
        assert not any("typo" in a for a in saved_facts["achievements"])
        print("• Achievement recognition verified: PASSED")

    print("\n===========================================================")
    print("PHASE 6.4 EMOTIONAL INTELLIGENCE SUITE: ALL TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_tests()
