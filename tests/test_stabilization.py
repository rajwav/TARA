import os
import sys
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.orchestrator import TARAOrchestrator
from tara.tools import registry
from tara.security import security_guard, RiskLevel
from tara.actions.file_actions import create_folder, create_file, list_directory, get_file_info
from tara.actions.system_actions import get_battery_status, get_memory_usage, get_storage_usage, get_running_apps


def run_stabilization_tests():
    print("===========================================================")
    print("TARA CORE STABILIZATION REGRESSION SUITE")
    print("===========================================================")

    # 1. Normal Chat Test
    print("\n[Test 1: Normal Chat & Single-Request API Flow]")
    orch = TARAOrchestrator(mode="text")
    reply = orch.process_turn("Hello TARA, confirm systems are operational in one sentence.")
    print("• Orchestrator Reply:", reply.strip())
    assert len(reply) > 0, "Normal chat must return a non-empty response"
    print("• Normal Chat Test: PASSED")

    # 2. Battery Status Tool
    print("\n[Test 2: Battery Status Tool Execution]")
    batt = registry.execute("get_battery_status", {})
    print("• Battery Result:", batt)
    assert "%" in batt or "Battery" in batt
    print("• Battery Status Tool: PASSED")

    # 3. RAM & Storage System Metrics Tool
    print("\n[Test 3: RAM & Storage Metrics Tools]")
    mem = registry.execute("get_memory_usage", {})
    print("• Memory Result:\n ", mem)
    assert "RAM" in mem and "GB" in mem

    storage = registry.execute("get_storage_usage", {})
    print("• Storage Result:\n ", storage)
    assert "Storage" in storage and "GB" in storage
    print("• RAM & Storage Metrics Tools: PASSED")

    # 4. Running Apps Tool
    print("\n[Test 4: Running Applications Tool]")
    apps = registry.execute("get_running_apps", {})
    print("• Running Apps Result preview:\n ", apps[:120], "...")
    assert "Active Applications" in apps
    print("• Running Applications Tool: PASSED")

    # 5. File Action Tools (create folder, create file, list, info)
    print("\n[Test 5: Safe File Action Tools]")
    with tempfile.TemporaryDirectory() as temp_dir:
        folder_p = os.path.join(temp_dir, "stabilization_test")
        res_folder = registry.execute("create_folder", {"path": folder_p})
        print("• create_folder tool:", res_folder)
        assert os.path.exists(folder_p)

        file_p = os.path.join(folder_p, "core_status.log")
        res_file = registry.execute("create_file", {"path": file_p, "content": "Core is stable and error-free."})
        print("• create_file tool:", res_file)
        assert os.path.exists(file_p)

        res_info = registry.execute("get_file_info", {"path": file_p})
        print("• get_file_info tool:\n ", res_info)
        assert "core_status.log" in res_info

        res_list = registry.execute("list_directory", {"path": folder_p})
        print("• list_directory tool:\n ", res_list)
        assert "core_status.log" in res_list

    print("• Safe File Action Tools: PASSED")

    # 6. Performance & Resource Footprint
    print("\n[Test 6: Resource & Memory Benchmark]")
    ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    print(f"• Peak Process RSS: {ram_mb:.2f} MB (Target: < 120 MB)")
    assert ram_mb < 120.0, "Core RAM footprint must remain low"
    print("• Resource Benchmark: PASSED")

    print("\n===========================================================")
    print("TARA STABILIZATION REGRESSION SUITE: 100% OF TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_stabilization_tests()
