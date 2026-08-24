import os
import re
import shutil
import subprocess
import logging
from typing import Optional
from tara.security import security_guard, RiskLevel

logger = logging.getLogger("tara.actions.system")


def get_cpu_usage() -> str:
    """Retrieve macOS CPU usage breakdown and logical core count."""
    try:
        cores = os.cpu_count() or 8
        load_1, load_5, load_15 = os.getloadavg()

        # Fast non-blocking CPU usage calculation via ps
        ps_out = subprocess.check_output(["ps", "-A", "-o", "%cpu"], timeout=2).decode("utf-8", errors="ignore")
        total_cpu = sum(float(x.strip()) for x in ps_out.splitlines()[1:] if x.strip())
        pct_usage = min(100.0, total_cpu / cores)

        res = (
            f"**System CPU Metrics ({cores} cores):**\n"
            f"- **Active CPU Utilization:** {pct_usage:.1f}%\n"
            f"- **System Load Averages:** {load_1:.2f} (1m), {load_5:.2f} (5m), {load_15:.2f} (15m)"
        )
        security_guard.log_action("get_cpu_usage", {}, RiskLevel.LOW, "success")
        return res

    except Exception as e:
        security_guard.log_action("get_cpu_usage", {}, RiskLevel.LOW, "failed")
        return f"Error reading CPU usage: {e}"


def get_memory_usage() -> str:
    """Retrieve macOS RAM usage metrics (Total, Used, Available, Compressed)."""
    try:
        # Get total RAM in bytes
        sysctl_mem = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=2).decode().strip())
        total_ram_gb = sysctl_mem / (1024 ** 3)

        # Get page size
        try:
            ps_out = subprocess.check_output(["pagesize"], timeout=2).decode().strip()
            page_size = int(ps_out) if ps_out.isdigit() else 16384
        except Exception:
            page_size = 16384

        # Read vm_stat
        vm_out = subprocess.check_output(["vm_stat"], timeout=2).decode("utf-8", errors="ignore")
        pages_free = 0
        pages_active = 0
        pages_inactive = 0
        pages_speculative = 0
        pages_wired = 0
        pages_compressed = 0

        for line in vm_out.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                k = parts[0].strip()
                val_digits = re.sub(r"[^0-9]", "", parts[1])
                if val_digits:
                    v = int(val_digits)
                    if "Pages free" in k:
                        pages_free = v
                    elif "Pages active" in k:
                        pages_active = v
                    elif "Pages inactive" in k:
                        pages_inactive = v
                    elif "Pages speculative" in k:
                        pages_speculative = v
                    elif "Pages wired down" in k:
                        pages_wired = v
                    elif "Pages occupied by compressor" in k:
                        pages_compressed = v

        used_ram_gb = ((pages_active + pages_wired + pages_compressed) * page_size) / (1024 ** 3)
        free_ram_gb = ((pages_free + pages_inactive + pages_speculative) * page_size) / (1024 ** 3)
        pct_used = (used_ram_gb / total_ram_gb) * 100

        res = (
            f"**macOS Unified Memory Usage:**\n"
            f"- **Total RAM:** {total_ram_gb:.1f} GB\n"
            f"- **In Use:** {used_ram_gb:.2f} GB ({pct_used:.1f}%)\n"
            f"- **Available:** {free_ram_gb:.2f} GB"
        )
        security_guard.log_action("get_memory_usage", {}, RiskLevel.LOW, "success")
        return res

    except Exception as e:
        security_guard.log_action("get_memory_usage", {}, RiskLevel.LOW, "failed")
        return f"Error reading memory usage: {e}"


def get_storage_usage() -> str:
    """Retrieve primary disk storage statistics."""
    try:
        du = shutil.disk_usage("/")
        total_gb = du.total / (1024 ** 3)
        used_gb = du.used / (1024 ** 3)
        free_gb = du.free / (1024 ** 3)
        pct_used = (du.used / du.total) * 100

        res = (
            f"**Primary Disk Storage (`/`):**\n"
            f"- **Total Space:** {total_gb:.1f} GB\n"
            f"- **Used Space:** {used_gb:.1f} GB ({pct_used:.1f}%)\n"
            f"- **Free Available:** {free_gb:.1f} GB"
        )
        security_guard.log_action("get_storage_usage", {}, RiskLevel.LOW, "success")
        return res

    except Exception as e:
        security_guard.log_action("get_storage_usage", {}, RiskLevel.LOW, "failed")
        return f"Error reading storage usage: {e}"


def get_running_apps() -> str:
    """List currently active running GUI applications on macOS."""
    try:
        apps = []
        # Method 1: lsappinfo visibleprocesslist (fast, non-intrusive)
        try:
            ls_out = subprocess.check_output(["lsappinfo", "visibleprocesslist"], timeout=2).decode().strip()
            for token in ls_out.split():
                m = re.search(r'"([^"]+)"', token)
                if m:
                    app_name = m.group(1).replace("_", " ")
                    if app_name not in apps:
                        apps.append(app_name)
        except Exception:
            pass

        # Method 2: ps inspection fallback
        if not apps:
            ps_out = subprocess.check_output(["ps", "-x", "-o", "comm"], timeout=2).decode()
            for line in ps_out.splitlines():
                if ".app/" in line:
                    parts = line.split(".app")[0].split("/")
                    name = parts[-1]
                    if name not in apps and not name.startswith("."):
                        apps.append(name)

        if not apps:
            return "No active GUI applications detected."

        res = f"**Currently Active Applications ({len(apps)}):**\n" + "\n".join(f"- {a}" for a in apps)
        security_guard.log_action("get_running_apps", {}, RiskLevel.LOW, "success")
        return res

    except Exception as e:
        security_guard.log_action("get_running_apps", {}, RiskLevel.LOW, "failed")
        return f"Error reading running apps: {e}"


def get_battery_status() -> str:
    """Retrieve current macOS battery charge level and charging status."""
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"], timeout=2).decode("utf-8", errors="ignore")
        match = re.search(r"(\d+)%", out)
        if match:
            pct = match.group(1)
            state = "charging" if "charging" in out.lower() or "ac attached" in out.lower() else "discharging"
            time_match = re.search(r"(\d+:\d+)\s+remaining", out)
            time_str = f" ({time_match.group(1)} remaining)" if time_match else ""
            res = f"Battery is at {pct}% ({state}){time_str}."
        else:
            res = f"Battery status: {out.strip()}"

        security_guard.log_action("get_battery_status", {}, RiskLevel.LOW, "success")
        return res

    except Exception as e:
        security_guard.log_action("get_battery_status", {}, RiskLevel.LOW, "failed")
        return f"Unable to read battery status: {e}"
