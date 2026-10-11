"""
AirControl — File System & Known Folder Navigation Subsystem
Safely resolves Windows known folders, project directory, and latest screenshots.
Strictly non-destructive (read and open only).
"""

import glob
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

KNOWN_FOLDERS: Dict[str, Path] = {
    "downloads": Path(os.path.expanduser("~/Downloads")),
    "documents": Path(os.path.expanduser("~/Documents")),
    "desktop": Path(os.path.expanduser("~/Desktop")),
    "pictures": Path(os.path.expanduser("~/Pictures")),
    "screenshots": Path(os.path.expanduser("~/Pictures/Screenshots")),
    "project": PROJECT_ROOT,
    "my project folder": PROJECT_ROOT,
    "project folder": PROJECT_ROOT,
}


class FileActions:
    """
    Safely resolves and opens user directories and specific files
    using the native Windows shell without command-line injection.
    """

    def __init__(self, opener_fn: Optional[Callable[[str], any]] = None):
        self.opener_fn = opener_fn or os.startfile

    def open_known_folder(self, folder_key: str) -> Tuple[bool, str, str]:
        """Opens a standard Windows user directory."""
        key = folder_key.lower().strip()
        folder_path = KNOWN_FOLDERS.get(key)

        if not folder_path or not folder_path.exists():
            return False, f"Directory '{folder_key}' does not exist on this machine.", f"Open {folder_key.title()}"

        try:
            self.opener_fn(str(folder_path))
            return True, f"Action: Open {folder_path.name} Folder", f"Open {folder_path.name}"
        except Exception as exc:
            return False, f"Error opening folder '{folder_key}': {exc}", f"Open {folder_key.title()}"

    def open_latest_screenshot(self) -> Tuple[bool, str, str]:
        """Locates the most recently modified screenshot file and opens it."""
        search_dirs = [
            KNOWN_FOLDERS["screenshots"],
            KNOWN_FOLDERS["pictures"],
            KNOWN_FOLDERS["desktop"],
        ]

        found_files: List[Tuple[float, str]] = []
        extensions = ("*.png", "*.jpg", "*.jpeg")

        for d in search_dirs:
            if d.exists():
                for ext in extensions:
                    for f in glob.glob(str(d / ext)):
                        try:
                            # Prioritize files with 'screenshot' in the name
                            mtime = os.path.getmtime(f)
                            if "screenshot" in os.path.basename(f).lower():
                                mtime += 100000.0  # Weight screenshots higher
                            found_files.append((mtime, f))
                        except OSError:
                            pass

        if not found_files:
            return False, "No screenshots found in Pictures or Desktop.", "Open Screenshot"

        found_files.sort(key=lambda x: x[0], reverse=True)
        latest_file = found_files[0][1]

        try:
            self.opener_fn(latest_file)
            name = os.path.basename(latest_file)
            return True, f"Action: Open Latest Screenshot ({name})", f"Open {name}"
        except Exception as exc:
            return False, f"Error opening screenshot: {exc}", "Open Screenshot"

    def find_latest_screenshot(self) -> Tuple[bool, str, str]:
        """Find the newest image in the usual screenshot folders without opening it."""
        candidates: List[Tuple[float, Path]] = []
        for folder_key in ("screenshots", "pictures", "desktop"):
            folder = KNOWN_FOLDERS[folder_key]
            if not folder.is_dir():
                continue
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if entry.is_file() and Path(entry.name).suffix.lower() in {
                            ".png", ".jpg", ".jpeg"
                        }:
                            candidates.append((entry.stat().st_mtime, Path(entry.path)))
            except OSError as exc:
                return False, f"Could not inspect {folder}: {exc}", "Find Screenshot"

        if not candidates:
            return False, "No screenshots found in Pictures, Screenshots, or Desktop.", "Find Screenshot"
        candidates.sort(key=lambda item: item[0], reverse=True)
        path = candidates[0][1]
        return True, f"Found latest screenshot: {path}", "Find Screenshot"

    def find_file(
        self,
        query: str,
        folder_key: str = "documents",
        cancel_event=None,
        max_directories: int = 300,
        max_depth: int = 4,
        max_results: int = 5,
    ) -> Tuple[bool, str, str]:
        """Search selected user folders with strict directory and depth bounds."""
        normalized_query = query.casefold().strip()
        if not normalized_query:
            return False, "A file name or type is required for search.", "Find File"

        search_roots = {
            "downloads": ("downloads",),
            "documents": ("documents",),
            "desktop": ("desktop",),
            "pictures": ("pictures", "screenshots"),
            "screenshots": ("screenshots", "pictures"),
            "project": ("project",),
            "project folder": ("project",),
        }
        keys = search_roots.get(folder_key.casefold().strip())
        if keys is None:
            return False, f"Unsupported search folder: {folder_key}", "Find File"

        ignored_directories = {
            ".git", ".venv", ".venv312", "node_modules", "__pycache__",
            ".pytest_cache", "models",
        }
        pending = [(KNOWN_FOLDERS[key], 0) for key in keys]
        visited = 0
        matches: List[Path] = []
        scan_errors: List[str] = []

        while pending and visited < max_directories and len(matches) < max_results:
            if cancel_event is not None and cancel_event.is_set():
                return False, "File search cancelled.", "Find File"

            directory, depth = pending.pop()
            if not directory.is_dir():
                continue
            visited += 1
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if cancel_event is not None and cancel_event.is_set():
                            return False, "File search cancelled.", "Find File"
                        try:
                            if entry.is_file(follow_symlinks=False):
                                if normalized_query in entry.name.casefold():
                                    matches.append(Path(entry.path))
                                    if len(matches) >= max_results:
                                        break
                            elif (
                                depth < max_depth
                                and entry.is_dir(follow_symlinks=False)
                                and entry.name.casefold() not in ignored_directories
                                and not entry.name.startswith(".")
                            ):
                                pending.append((Path(entry.path), depth + 1))
                        except OSError as exc:
                            scan_errors.append(f"{entry.path}: {exc}")
            except OSError as exc:
                scan_errors.append(f"{directory}: {exc}")

        if matches:
            paths = "\n".join(str(path) for path in matches)
            suffix = "\nSearch result limit reached." if len(matches) == max_results else ""
            return True, f"Found {len(matches)} matching file(s):\n{paths}{suffix}", "Find File"
        if cancel_event is not None and cancel_event.is_set():
            return False, "File search cancelled.", "Find File"
        if scan_errors and visited == 0:
            return False, f"Could not search selected folders: {scan_errors[0]}", "Find File"
        bounded_note = (
            " Search stopped at its directory limit." if pending and visited >= max_directories else ""
        )
        return False, f"No file matching '{query}' was found in the selected folders.{bounded_note}", "Find File"

    def open_specific_file(self, filename_or_path: str) -> Tuple[bool, str, str]:
        """
        Safely searches for and opens an unambiguous file (e.g. PDF, project document).
        Never modifies or deletes files.
        """
        target = Path(filename_or_path)

        # 1. Direct path exists
        if target.is_file():
            try:
                self.opener_fn(str(target))
                return True, f"Action: Open File '{target.name}'", f"Open {target.name}"
            except Exception as exc:
                return False, f"Error opening file: {exc}", "Open File"

        # 2. Search only bounded, common user folders; never scan whole disks.
        matches = []
        for folder_key in ("documents", "downloads", "desktop", "project"):
            success, message, _ = self.find_file(
                filename_or_path, folder_key, max_directories=120, max_depth=3, max_results=2
            )
            if success:
                for line in message.splitlines()[1:]:
                    path = Path(line)
                    if path.is_file() and path not in matches:
                        matches.append(path)
            if len(matches) > 1:
                break

        if len(matches) == 1:
            chosen = matches[0]
            try:
                self.opener_fn(str(chosen))
                return True, f"Action: Open File '{chosen.name}'", f"Open {chosen.name}"
            except Exception as exc:
                return False, f"Error opening file: {exc}", "Open File"

        if len(matches) > 1:
            cands = ", ".join(f"'{m.name}'" for m in matches[:4])
            return False, f"Multiple matching files found: {cands}. Please specify.", "Open File"

        return False, f"File '{filename_or_path}' could not be found.", "Open File"

    def open_recycle_bin(self) -> Tuple[bool, str, str]:
        """Open the Windows Recycle Bin via its registered shell namespace."""
        if os.name != "nt":
            return False, "The Recycle Bin action is available only on Windows.", "Recycle Bin"
        try:
            self.opener_fn("shell:RecycleBinFolder")
            return True, "Action: Open Recycle Bin", "Recycle Bin"
        except Exception as exc:
            return False, f"Could not open the Recycle Bin: {exc}", "Recycle Bin"
