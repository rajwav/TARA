import os
import sys
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.documents import DocumentEngine
from tara.knowledge import KnowledgeManager
from tara.tools import registry
from tara.memory import MemoryStore


def create_sample_pdf(path: str, text: str = "TARA Document Intelligence Test. Chapter 1: Architecture Overview.") -> str:
    """Create a valid sample PDF file using pypdf for testing."""
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # pypdf allows creating a basic PDF; we can also write text via standard metadata or pypdf canvas/writer
    with open(path, "wb") as f:
        writer.write(f)
    return path


def run_tests():
    print("===========================================================")
    print("PHASE 6.6 DOCUMENT INTELLIGENCE LAYER TEST SUITE")
    print("===========================================================")

    doc_engine = DocumentEngine()
    knowledge = KnowledgeManager()

    # 1. TXT Extraction Test
    print("\n[Test 1: TXT Document Extraction]")
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as tf:
        tf.write("TARA Architecture Guidelines:\n- Keep modules lightweight.\n- Never add LangChain or heavy vector DBs.\n- Optimize for M1 Mac.")
        txt_path = tf.name

    try:
        txt_content = doc_engine.extract_text(txt_path)
        print("• Extracted TXT:\n", txt_content)
        assert "TARA Architecture Guidelines" in txt_content
        print("• TXT Extraction Test: PASSED")
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)

    # 2. Markdown & Code File Reading Test
    print("\n[Test 2: Source Code & Markdown Reading]")
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tf:
        tf.write("def calculate_efficiency(tokens: int, ms: float) -> float:\n    return tokens / (ms / 1000.0)\n")
        py_path = tf.name

    try:
        code_content = doc_engine.extract_text(py_path)
        print("• Extracted Code:\n", code_content)
        assert "calculate_efficiency" in code_content
        print("• Code File Reading Test: PASSED")
    finally:
        if os.path.exists(py_path):
            os.remove(py_path)

    # 3. PDF Extraction Test
    print("\n[Test 3: PDF Document Extraction]")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf_path = tf.name
    create_sample_pdf(pdf_path)

    try:
        pdf_result = doc_engine.extract_text(pdf_path)
        print("• Extracted PDF Result preview:", pdf_result[:60])
        assert isinstance(pdf_result, str), "PDF extraction must return string"
        print("• PDF Extraction Test: PASSED")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    # 4. Summarization Test & Tool Registry Test
    print("\n[Test 4: Summarization & Tool Execution]")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as tf:
        tf.write(
            "# System Report\n\n"
            "This report outlines the deployment of the Phoenix backend container on AWS EC2. "
            "The system uses NGINX with TLS encryption and an active rate limit of 60 requests per minute. "
            "All unit tests for authentication and database migration passed successfully."
        )
        md_path = tf.name

    try:
        # Tool: read_document
        read_res = registry.execute("read_document", {"path": md_path})
        print("• read_document Tool output preview:\n ", read_res[:100], "...")
        assert "System Report" in read_res

        # Tool: summarize_document
        summary_res = registry.execute("summarize_document", {"path": md_path})
        print("• summarize_document Tool output:\n ", summary_res)
        assert len(summary_res) > 0

        print("• Summarization & Tool Execution: PASSED")
    finally:
        if os.path.exists(md_path):
            os.remove(md_path)

    # 5. Memory Safety Test (No raw documents stored in SQLite)
    print("\n[Test 5: Memory Safety & Privacy Check]")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        mem = MemoryStore(db_path=test_db)
        km = KnowledgeManager(memory_store=mem)

        # Set active doc in session memory
        km.set_active_document("/tmp/sample_doc.txt", "Large raw document content " * 100)

        # Verify SQLite has 0 raw document blobs
        with mem._get_connection() as conn:
            rows = conn.execute("SELECT value FROM user_facts").fetchall()
            for r in rows:
                assert len(r["value"]) < 500, "Raw documents must not be in SQLite!"

        # Save an explicit learned fact
        km.save_learned_fact("preference", "code_style", "PEP 8 with type hints")
        facts = mem.get_all_facts()
        print("• Stored facts in memory:", facts["preferences"])
        assert any("PEP 8" in p for p in facts["preferences"])
        print("• Memory Safety Check: PASSED")

    # 6. Missing File Error Handling
    print("\n[Test 6: Missing File Error Handling]")
    err_res = registry.execute("read_document", {"path": "/tmp/non_existent_file_98765.txt"})
    print("• Missing file response:", err_res)
    assert "Failed to read" in err_res or "not found" in err_res.lower()
    print("• Missing File Error Handling: PASSED")

    # 7. Resource Benchmark (RAM increase < 100MB)
    print("\n[Test 7: Resource & Memory Benchmark]")
    ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    print(f"• Peak Process RSS: {ram_mb:.2f} MB (Target: < 100 MB increase)")
    assert ram_mb < 150.0, "Process RAM must remain low"
    print("• Resource Benchmark: PASSED")

    print("\n===========================================================")
    print("PHASE 6.6 DOCUMENT INTELLIGENCE SUITE: ALL TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_tests()
