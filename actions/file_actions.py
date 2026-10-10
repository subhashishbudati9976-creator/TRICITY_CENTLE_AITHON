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

        # 2. Search common user directories for the filename
        q = filename_or_path.strip().lower()
        search_locations = [
            PROJECT_ROOT,
            KNOWN_FOLDERS["downloads"],
            KNOWN_FOLDERS["documents"],
            KNOWN_FOLDERS["desktop"],
        ]

        matched: List[Path] = []
        for loc in search_locations:
            if loc.exists():
                for p in loc.iterdir():
                    if p.is_file() and q in p.name.lower():
                        matched.append(p)

        if len(matched) == 1:
            chosen = matched[0]
            try:
                self.opener_fn(str(chosen))
                return True, f"Action: Open File '{chosen.name}'", f"Open {chosen.name}"
            except Exception as exc:
                return False, f"Error opening file: {exc}", "Open File"

        if len(matched) > 1:
            cands = ", ".join(f"'{m.name}'" for m in matched[:4])
            return False, f"Multiple matching files found: {cands}. Please specify.", "Open File"

        return False, f"File '{filename_or_path}' could not be found.", "Open File"
