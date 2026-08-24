import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Optional
from tara.security import security_guard, RiskLevel

logger = logging.getLogger("tara.actions.app")

APP_ALIASES = {
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "brave": "Brave Browser",
    "brave browser": "Brave Browser",
    "safari": "Safari",
    "calc": "Calculator",
    "calculator": "Calculator",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "iterm2": "iTerm2",
    "notes": "Notes",
    "finder": "Finder",
    "settings": "System Settings",
    "system settings": "System Settings",
    "system preferences": "System Settings",
    "calendar": "Calendar",
    "messages": "Messages",
    "music": "Music",
    "mail": "Mail",
    "preview": "Preview",
}


def open_application(app_name: str) -> str:
    """Launch or focus a macOS application by name or common alias."""
    if not app_name or not app_name.strip():
        return "Error: Application name cannot be empty."

    raw_name = app_name.strip()
    target_app = APP_ALIASES.get(raw_name.lower(), raw_name)

    try:
        # Launch macOS app using 'open -a <app_name>'
        result = subprocess.run(["open", "-a", target_app], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            security_guard.log_action("open_application", {"app_name": target_app}, RiskLevel.LOW, "success")
            return f"Successfully opened `{target_app}`."
        else:
            err_msg = result.stderr.strip() or f"Application '{target_app}' not found."
            security_guard.log_action("open_application", {"app_name": target_app}, RiskLevel.LOW, "failed")
            return f"Failed to open '{target_app}': {err_msg}"

    except Exception as e:
        security_guard.log_action("open_application", {"app_name": target_app}, RiskLevel.LOW, "failed")
        return f"Error launching application '{target_app}': {e}"


def open_project_folder(path: str = ".") -> str:
    """Open a project directory or folder in macOS Finder."""
    try:
        resolved = security_guard.validate_path(path, allow_write=False)
        if not resolved.exists():
            return f"Error: Project folder '{path}' does not exist."

        result = subprocess.run(["open", str(resolved)], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            security_guard.log_action("open_project_folder", {"path": str(resolved)}, RiskLevel.LOW, "success")
            return f"Successfully opened folder `{resolved.name or str(resolved)}` in Finder."
        else:
            security_guard.log_action("open_project_folder", {"path": str(resolved)}, RiskLevel.LOW, "failed")
            return f"Failed to open folder '{resolved}': {result.stderr.strip()}"

    except Exception as e:
        security_guard.log_action("open_project_folder", {"path": path}, RiskLevel.LOW, "failed")
        return f"Error opening project folder '{path}': {e}"


def open_url(url: str) -> str:
    """Open a validated URL in the user's default browser."""
    if not url or not url.strip():
        return "Error: URL cannot be empty."

    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        clean_url = f"https://{clean_url}"

    try:
        result = subprocess.run(["open", clean_url], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            security_guard.log_action("open_url", {"url": clean_url}, RiskLevel.LOW, "success")
            return f"Successfully opened URL: {clean_url}"
        else:
            security_guard.log_action("open_url", {"url": clean_url}, RiskLevel.LOW, "failed")
            return f"Failed to open URL '{clean_url}': {result.stderr.strip()}"

    except Exception as e:
        security_guard.log_action("open_url", {"url": clean_url}, RiskLevel.LOW, "failed")
        return f"Error opening URL '{clean_url}': {e}"
