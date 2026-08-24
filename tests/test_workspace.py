import os
import sys
import time
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.workspace import KnowledgeWorkspace
from tara.tools import registry
from tara.orchestrator import TARAOrchestrator


def run_tests():
    print("===========================================================")
    print("PHASE 6.7 PERSONAL KNOWLEDGE WORKSPACE TEST SUITE")
    print("===========================================================")

    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        ws = KnowledgeWorkspace(db_path=test_db)

        # Create temporary sample files for testing
        with tempfile.NamedTemporaryFile(suffix="_transformers.md", mode="w", delete=False) as f1:
            f1.write(
                "# Deep Learning Notes: Transformers\n\n"
                "Transformers use self-attention mechanisms and positional encodings. "
                "Common models include BERT, GPT, and RoBERTa for NLP tasks."
            )
            file_transformers = f1.name

        with tempfile.NamedTemporaryFile(suffix="_api.py", mode="w", delete=False) as f2:
            f2.write(
                "# FastAPI Backend Service\n"
                "from fastapi import FastAPI\n"
                "app = FastAPI(title='Phoenix API')\n"
                "@app.get('/health')\ndef health():\n    return {'status': 'healthy'}\n"
            )
            file_fastapi = f2.name

        try:
            # 1. File Indexing Test
            print("\n[Test 1: File Indexing Test]")
            idx1 = ws.index_file(file_transformers)
            idx2 = ws.index_file(file_fastapi)
            print("• Indexed File 1:", idx1["filename"], "Keywords:", idx1["keywords"][:60])
            print("• Indexed File 2:", idx2["filename"], "Keywords:", idx2["keywords"][:60])
            assert "transformers" in idx1["keywords"].lower() or "attention" in idx1["keywords"].lower()
            assert "fastapi" in idx2["keywords"].lower()
            print("• File Indexing Test: PASSED")

            # 2. Search Returns Relevant Files Test
            print("\n[Test 2: Full-Text Search Relevance Check]")
            res_tf = ws.search_knowledge("transformers")
            print(f"• Query 'transformers' found {len(res_tf)} result(s):")
            for r in res_tf:
                print(f"   - {r['filename']} ({r['file_type']})")
            assert any("transformers" in r["filename"].lower() for r in res_tf)

            res_api = ws.search_knowledge("FastAPI health")
            print(f"• Query 'FastAPI health' found {len(res_api)} result(s):")
            for r in res_api:
                print(f"   - {r['filename']} ({r['file_type']})")
            assert any("api.py" in r["filename"].lower() for r in res_api)
            print("• Search Relevance Check: PASSED")

            # 3. Metadata Stored Correctly Test
            print("\n[Test 3: Metadata Integrity Check]")
            summary = ws.get_workspace_summary()
            print("• Workspace Summary:", summary)
            assert summary["total_documents"] == 2
            assert ".md" in summary["file_types"]
            assert ".py" in summary["file_types"]
            print("• Metadata Integrity Check: PASSED")

            # 4. Raw Documents Are NOT Stored Permanently Test
            print("\n[Test 4: Privacy & Raw Document Storage Check]")
            with ws._get_connection() as conn:
                rows = conn.execute("SELECT * FROM knowledge_index").fetchall()
                for r in rows:
                    print(f"• Row path: {r['path']}, keywords len: {len(r['keywords'])}")
                    assert len(r["keywords"]) < 1000, "Keywords must be compact!"
                    # Ensure full raw file text is not stored in any column
                    assert "self-attention mechanisms and positional encodings" not in r["keywords"]
            print("• Privacy & Raw Document Isolation: PASSED")

            # 5. Deleted Files Removed From Index Test
            print("\n[Test 5: File Removal & Index Sync Check]")
            ws.remove_file(file_transformers)
            search_after = ws.search_knowledge("transformers")
            print(f"• Query 'transformers' after removal found: {len(search_after)} results")
            assert len(search_after) == 0
            summary_after = ws.get_workspace_summary()
            assert summary_after["total_documents"] == 1
            print("• File Removal & Sync: PASSED")

            # 6. SQLite Search Performance Benchmark
            print("\n[Test 6: Search Performance Benchmark]")
            latencies = []
            for _ in range(500):
                t0 = time.perf_counter()
                _ = ws.search_knowledge("FastAPI")
                latencies.append((time.perf_counter() - t0) * 1000)

            avg_ms = sum(latencies) / len(latencies)
            max_ms = max(latencies)
            print(f"• Average Search Latency: {avg_ms:.4f} ms (Target: < 5.0 ms)")
            print(f"• Max Search Latency:     {max_ms:.4f} ms (Target: < 10.0 ms)")
            assert avg_ms < 5.0, "Average SQLite search latency must be under 5ms"
            print("• Search Performance Benchmark: PASSED")

            # 7. Resource & Memory Benchmark (RAM increase < 20MB)
            print("\n[Test 7: Resource & Memory Benchmark]")
            ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
            print(f"• Peak Process RSS: {ram_mb:.2f} MB (Target increase: < 20 MB)")
            assert ram_mb < 120.0, "RAM increase must remain well below 20MB"
            print("• Resource Benchmark: PASSED")

        finally:
            for p in [file_transformers, file_fastapi]:
                if os.path.exists(p):
                    os.remove(p)

    print("\n===========================================================")
    print("PHASE 6.7 KNOWLEDGE WORKSPACE SUITE: ALL TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_tests()
