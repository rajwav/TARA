import os
import sys
import time
import base64
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.screen_capture import ScreenCapture
from tara.vision import VisionEngine, GroqVisionProvider, OllamaVisionProvider
from tara.tools import registry
from tara.memory import MemoryStore
from tara.orchestrator import TARAOrchestrator


def create_dummy_png(path: str) -> str:
    """Create a minimal valid 1x1 PNG for testing without external image libraries."""
    # Standard 1x1 transparent PNG binary bytes
    png_bytes = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    with open(path, "wb") as f:
        f.write(png_bytes)
    return path


def run_tests():
    print("===========================================================")
    print("PHASE 6.5 VISION INTELLIGENCE LAYER TEST SUITE")
    print("===========================================================")

    sc = ScreenCapture()
    engine = VisionEngine()

    # 1. Screenshot Capture Test
    print("\n[Test 1: Screenshot Capture Test]")
    fd, temp_img = tempfile.mkstemp(prefix="tara_test_cap_", suffix=".png")
    os.close(fd)
    create_dummy_png(temp_img)

    captured = sc.capture_screen(temp_img)
    print(f"• Captured path: {captured} (Exists: {os.path.exists(temp_img)})")
    assert captured is not None and os.path.exists(captured), "Screenshot capture must succeed or return valid path"
    sc.cleanup(temp_img)
    assert not os.path.exists(temp_img), "Screenshot cleanup must remove temporary file"
    print("• Screenshot Capture Test: PASSED")

    # 2. Image Processing Test with VisionEngine
    print("\n[Test 2: Image Processing Structured Response Test]")
    fd, sample_img = tempfile.mkstemp(prefix="tara_sample_", suffix=".png")
    os.close(fd)
    create_dummy_png(sample_img)

    try:
        analysis = engine.analyze_image(sample_img, question="What is in this test image?")
        print("• Structured Analysis Result:")
        print("  - Description:", analysis.get("description")[:100] if analysis.get("description") else "None")
        print("  - Issues:     ", analysis.get("issues"))
        print("  - Suggestions:", analysis.get("suggestions"))
        assert "description" in analysis, "Analysis must have 'description'"
        assert "issues" in analysis, "Analysis must have 'issues'"
        assert "suggestions" in analysis, "Analysis must have 'suggestions'"
        print("• Image Processing Test: PASSED")
    finally:
        sc.cleanup(sample_img)

    # 3. Tool Integration Test
    print("\n[Test 3: Tool Integration Test (analyze_screen)]")
    # Verify tool is registered in registry
    schemas = registry.get_schemas()
    tool_names = [s["function"]["name"] for s in schemas]
    print(f"• Registered tools: {tool_names}")
    assert "capture_screen" in tool_names, "capture_screen must be registered"
    assert "analyze_screen" in tool_names, "analyze_screen must be registered"

    tool_result = registry.execute("analyze_screen", {"question": "Check my screen"})
    print("• Tool Execution Result Preview:\n", tool_result[:150], "...")
    assert len(tool_result) > 0, "Tool execution must return result"
    print("• Tool Integration Test: PASSED")

    # 4. Memory Safety Test (No images stored permanently)
    print("\n[Test 4: Memory Safety & Privacy Check]")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        mem = MemoryStore(db_path=test_db)
        
        # Test remembering user preference vs temporary image
        mem.extract_and_save_facts("I prefer dark UI themes for coding")
        facts = mem.get_all_facts()
        print("• User Facts stored:", facts["preferences"])
        assert any("dark UI themes" in p for p in facts["preferences"]), "User preference should be retained"

        # Verify no image binary / base64 is in user_facts
        with mem._get_connection() as conn:
            rows = conn.execute("SELECT value FROM user_facts").fetchall()
            for r in rows:
                val = r["value"]
                assert not val.startswith("data:image"), "Base64 image must not be in user_facts!"
                assert len(val) < 1000, "Large image blobs must not be in user_facts!"
        print("• Memory Safety & Privacy Check: PASSED")

    # 5. Resource & Memory Benchmark Test
    print("\n[Test 5: Resource & Memory Benchmark]")
    ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    print(f"• Peak RSS Memory: {ram_mb:.2f} MB (Target: < 500 MB)")
    assert ram_mb < 500.0, "Vision activation RAM must be < 500MB"
    print("• Resource Benchmark: PASSED")

    # 6. Error Handling Test
    print("\n[Test 6: Error Handling & Graceful Fallback]")
    # Missing file
    err1 = engine.analyze_image("/tmp/non_existent_image_12345.png")
    print("• Missing file response:", err1["description"])
    assert "not found" in err1["description"].lower()

    # Empty file
    fd, empty_img = tempfile.mkstemp(prefix="tara_empty_", suffix=".png")
    os.close(fd)
    try:
        err2 = engine.analyze_image(empty_img)
        print("• Empty file response:", err2["description"])
        assert "empty" in err2["description"].lower()
    finally:
        sc.cleanup(empty_img)

    print("• Error Handling Test: PASSED")

    print("\n===========================================================")
    print("PHASE 6.5 VISION INTELLIGENCE SUITE: ALL TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_tests()
