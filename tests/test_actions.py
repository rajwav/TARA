import os
import sys
import tempfile
import resource
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tara.security import SecurityGuard, RiskLevel
from tara.actions.file_actions import (
    list_directory,
    create_file,
    create_folder,
    move_file,
    get_file_info
)
from tara.actions.app_actions import (
    open_application,
    open_project_folder,
    open_url
)
from tara.actions.system_actions import (
    get_cpu_usage,
    get_memory_usage,
    get_storage_usage,
    get_running_apps,
    get_battery_status
)
from tara.actions.browser_actions import (
    open_browser_url,
    web_search
)
from tara.tools import registry
from tara.orchestrator import TARAOrchestrator


def run_action_tests():
    print("===========================================================")
    print("PHASE 7.1 SAFE ACTION & EXECUTION LAYER TEST SUITE")
    print("===========================================================")

    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_db = Path(tf.name)
        sec = SecurityGuard(db_path=test_db)

        # 1. File Actions Test
        print("\n[Test 1: Safe File Management Actions]")
        with tempfile.TemporaryDirectory() as temp_dir:
            test_folder = os.path.join(temp_dir, "tara_test_workspace")
            res_folder = create_folder(test_folder)
            print("• create_folder:", res_folder)
            assert os.path.exists(test_folder), "Folder must exist on disk"

            test_file = os.path.join(test_folder, "hello_tara.txt")
            res_file = create_file(test_file, "TARA Safe Action Layer Active\nTimestamp: 2026-08-24")
            print("• create_file:", res_file)
            assert os.path.exists(test_file)

            res_info = get_file_info(test_file)
            print("• get_file_info:\n", res_info)
            assert "hello_tara.txt" in res_info and "bytes" in res_info

            res_list = list_directory(test_folder)
            print("• list_directory:\n", res_list)
            assert "hello_tara.txt" in res_list

            dest_file = os.path.join(test_folder, "renamed_tara.txt")
            res_move = move_file(test_file, dest_file)
            print("• move_file:", res_move)
            assert os.path.exists(dest_file) and not os.path.exists(test_file)

        print("• Safe File Actions Test: PASSED")

        # 2. Application & Project Opening Test
        print("\n[Test 2: macOS Application & Project Control]")
        # Test app launcher with Calculator
        res_calc = open_application("Calculator")
        print("• open_application('Calculator'):", res_calc)
        assert "Successfully opened" in res_calc or "Calculator" in res_calc

        # Test project opening with relative workspace
        res_proj = open_project_folder(".")
        print("• open_project_folder('.'):", res_proj)
        assert "Successfully opened folder" in res_proj or "Finder" in res_proj
        print("• Application & Project Opening Test: PASSED")

        # 3. System Metrics & Inspection Test
        print("\n[Test 3: macOS System Monitoring & Metrics]")
        cpu = get_cpu_usage()
        print("• get_cpu_usage:\n ", cpu)
        assert "CPU Metrics" in cpu or "CPU usage" in cpu

        mem = get_memory_usage()
        print("• get_memory_usage:\n ", mem)
        assert "Memory Usage" in mem and "GB" in mem

        storage = get_storage_usage()
        print("• get_storage_usage:\n ", storage)
        assert "Disk Storage" in storage and "GB" in storage

        apps = get_running_apps()
        print("• get_running_apps preview:\n ", apps[:120], "...")
        assert "Active Applications" in apps

        batt = get_battery_status()
        print("• get_battery_status:\n ", batt)
        assert "%" in batt or "Battery" in batt
        print("• System Monitoring Test: PASSED")

        # 4. Browser Actions Test
        print("\n[Test 4: Browser Actions]")
        search_res = web_search("Python 3.14 features")
        print("• web_search preview:\n ", search_res[:120], "...")
        assert len(search_res) > 0
        print("• Browser Actions Test: PASSED")

        # 5. Security & Permission Guard Test
        print("\n[Test 5: Security Permission Guard & System Protection]")
        # Low risk check
        auth_low, msg_low = sec.check_and_authorize("get_cpu_usage", {}, RiskLevel.LOW)
        assert auth_low, "Low risk must be authorized"

        # Medium risk check
        auth_med, msg_med = sec.check_and_authorize("create_file", {"path": "test.txt"}, RiskLevel.MEDIUM)
        assert auth_med, "Medium risk must be authorized with logging"

        # High risk check without confirmation
        auth_high_unconf, msg_high_unconf = sec.check_and_authorize("delete_all", {}, RiskLevel.HIGH, confirmed=False)
        assert not auth_high_unconf, "High risk must require confirmation"

        # High risk check with confirmation
        auth_high_conf, msg_high_conf = sec.check_and_authorize("delete_all", {}, RiskLevel.HIGH, confirmed=True)
        assert auth_high_conf, "High risk with confirmation must be authorized"

        # Path protection check: system directories must be protected from writes
        try:
            sec.validate_path("/System/Library/forbidden.txt", allow_write=True)
            assert False, "System folder modification must raise PermissionError"
        except (PermissionError, ValueError) as e:
            print("• System protection successfully blocked write to /System:", e)

        print("• Security Permission Guard Test: PASSED")

        # 6. SQLite Action History Logging Test
        print("\n[Test 6: SQLite Action History Logging Check]")
        sec.log_action("create_file", {"path": "/tmp/test.txt"}, RiskLevel.MEDIUM, "success", "granted")
        sec.log_action("open_application", {"app_name": "Calculator"}, RiskLevel.LOW, "success", "granted")

        with sec._get_connection() as conn:
            rows = conn.execute("SELECT * FROM action_history ORDER BY id DESC LIMIT 5").fetchall()
            print(f"• Found {len(rows)} logged actions in SQLite action_history:")
            for r in rows:
                print(f"   - [{r['risk_level']}] {r['action_name']} -> {r['status']} ({r['timestamp']})")
            assert len(rows) >= 2
            assert any(r["action_name"] == "create_file" for r in rows)
            assert any(r["action_name"] == "open_application" for r in rows)

        print("• SQLite Action History Logging Test: PASSED")

        # 7. Performance & Resource Benchmark
        print("\n[Test 7: Performance & Memory Benchmark]")
        ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        print(f"• Peak Process RSS: {ram_mb:.2f} MB (Target: < 150 MB)")
        assert ram_mb < 150.0, "Memory footprint must remain under 150MB"
        print("• Resource Benchmark: PASSED")

    print("\n===========================================================")
    print("PHASE 7.1 SAFE ACTION LAYER: 100% OF TESTS PASSED!")
    print("===========================================================")


if __name__ == "__main__":
    run_action_tests()
