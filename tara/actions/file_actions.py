import os
import shutil
import datetime
import logging
from pathlib import Path
from typing import Optional
from tara.security import security_guard, RiskLevel

logger = logging.getLogger("tara.actions.file")


def list_directory(path: str = ".") -> str:
    """List files and subdirectories in the specified path with size and modification info."""
    try:
        target_dir = security_guard.validate_path(path, allow_write=False)
        if not target_dir.exists():
            return f"Error: Directory '{path}' does not exist."
        if not target_dir.is_dir():
            return f"Error: '{path}' is not a directory."

        entries = sorted(os.listdir(target_dir))
        if not entries:
            security_guard.log_action("list_directory", {"path": path}, RiskLevel.LOW, "success")
            return f"Directory '{path}' is empty."

        lines = [f"**Contents of '{target_dir.name or str(target_dir)}' ({len(entries)} items):**"]
        for entry in entries[:60]:
            full_p = target_dir / entry
            is_dir = full_p.is_dir()
            type_label = "[DIR]" if is_dir else "[FILE]"
            try:
                size_str = "" if is_dir else f" ({full_p.stat().st_size} bytes)"
                mtime = datetime.datetime.fromtimestamp(full_p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                lines.append(f"- {type_label} `{entry}`{size_str} — {mtime}")
            except Exception:
                lines.append(f"- {type_label} `{entry}`")

        if len(entries) > 60:
            lines.append(f"... and {len(entries) - 60} more items.")

        security_guard.log_action("list_directory", {"path": path}, RiskLevel.LOW, "success")
        return "\n".join(lines)

    except Exception as e:
        security_guard.log_action("list_directory", {"path": path}, RiskLevel.LOW, "failed")
        return f"Error listing directory '{path}': {e}"


def create_file(path: str, content: str = "") -> str:
    """Create a new file with the specified text content."""
    try:
        target_file = security_guard.validate_path(path, allow_write=True)
        # Create parent directories if they don't exist
        target_file.parent.mkdir(parents=True, exist_ok=True)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)

        security_guard.log_action("create_file", {"path": str(target_file), "length": len(content)}, RiskLevel.MEDIUM, "success")
        return f"Successfully created file `{target_file}` ({len(content)} characters written)."

    except Exception as e:
        security_guard.log_action("create_file", {"path": path}, RiskLevel.MEDIUM, "failed")
        return f"Error creating file '{path}': {e}"


def create_folder(path: str) -> str:
    """Create a new directory (and any necessary parent directories)."""
    try:
        target_dir = security_guard.validate_path(path, allow_write=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        security_guard.log_action("create_folder", {"path": str(target_dir)}, RiskLevel.MEDIUM, "success")
        return f"Successfully created folder `{target_dir}`."

    except Exception as e:
        security_guard.log_action("create_folder", {"path": path}, RiskLevel.MEDIUM, "failed")
        return f"Error creating folder '{path}': {e}"


def move_file(source: str, destination: str) -> str:
    """Move or rename a file or directory from source to destination."""
    try:
        src_path = security_guard.validate_path(source, allow_write=True)
        dst_path = security_guard.validate_path(destination, allow_write=True)

        if not src_path.exists():
            return f"Error: Source path '{source}' does not exist."

        # If destination is an existing directory, move into it
        if dst_path.is_dir():
            final_dst = dst_path / src_path.name
        else:
            final_dst = dst_path
            final_dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src_path), str(final_dst))

        security_guard.log_action(
            "move_file",
            {"source": str(src_path), "destination": str(final_dst)},
            RiskLevel.MEDIUM,
            "success"
        )
        return f"Successfully moved `{src_path.name}` to `{final_dst}`."

    except Exception as e:
        security_guard.log_action(
            "move_file",
            {"source": source, "destination": destination},
            RiskLevel.MEDIUM,
            "failed"
        )
        return f"Error moving file from '{source}' to '{destination}': {e}"


def get_file_info(path: str) -> str:
    """Retrieve detailed metadata about a file or directory."""
    try:
        target = security_guard.validate_path(path, allow_write=False)
        if not target.exists():
            return f"Error: Path '{path}' does not exist."

        stat = target.stat()
        is_dir = target.is_dir()
        size_bytes = stat.st_size
        size_kb = size_bytes / 1024
        ctime = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        info_lines = [
            f"**File Metadata for `{target.name}`:**",
            f"- **Type:** {'Directory' if is_dir else 'File'}",
            f"- **Full Path:** `{target}`",
            f"- **Size:** {size_bytes:,} bytes ({size_kb:.2f} KB)",
            f"- **Created:** {ctime}",
            f"- **Modified:** {mtime}",
            f"- **Permissions:** {oct(stat.st_mode)[-3:]}"
        ]

        security_guard.log_action("get_file_info", {"path": str(target)}, RiskLevel.LOW, "success")
        return "\n".join(info_lines)

    except Exception as e:
        security_guard.log_action("get_file_info", {"path": path}, RiskLevel.LOW, "failed")
        return f"Error retrieving file info for '{path}': {e}"
