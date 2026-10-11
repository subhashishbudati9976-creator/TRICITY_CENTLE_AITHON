"""Select installed interface fonts and privately load the bundled fallback."""

import ctypes
import logging
import os
import sys
from pathlib import Path


logger = logging.getLogger(__name__)


def _installed_windows_fonts() -> set[str]:
    if sys.platform != "win32":
        return set()
    import winreg

    names = set()
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    )
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for index in range(winreg.QueryInfoKey(key)[1]):
                    value_name, _, _ = winreg.EnumValue(key, index)
                    names.add(value_name.casefold())
        except OSError:
            continue
    return names


def _load_space_grotesk() -> bool:
    if sys.platform != "win32":
        return False
    font_path = Path(__file__).parent / "assets" / "fonts" / "SpaceGrotesk-Variable.ttf"
    if not font_path.is_file():
        logger.warning("Bundled Space Grotesk font is missing.")
        return False

    try:
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        add_font_resource = gdi32.AddFontResourceExW
        add_font_resource.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        add_font_resource.restype = ctypes.c_int
        if add_font_resource(str(font_path), 0x10, None) == 0:
            logger.warning("Could not register bundled Space Grotesk.")
            return False
        return True
    except (AttributeError, OSError) as exc:
        logger.warning("Could not register bundled Space Grotesk: %s", exc)
        return False


_installed_fonts_cache = _installed_windows_fonts()
_space_grotesk_loaded = _load_space_grotesk()


def _configured_or_fallback(variable: str, preferred: str, fallbacks: tuple[str, ...]) -> str:
    configured = os.environ.get(variable, "").strip()
    choices = ((configured,) if configured else ()) + (preferred,) + fallbacks
    for choice in choices:
        normalized = choice.casefold()
        if normalized == "space grotesk" and _space_grotesk_loaded:
            return "Space Grotesk"
        if normalized in _installed_fonts_cache or any(
            normalized in installed for installed in _installed_fonts_cache
        ):
            return choice
    if configured:
        logger.warning("%s=%r is not registered; using the documented fallback.", variable, configured)
    return fallbacks[-1]


DISPLAY_FONT = _configured_or_fallback(
    "AIRCONTROL_DISPLAY_FONT",
    "Neue Haas Grotesk",
    ("Space Grotesk", "Segoe UI"),
)
BODY_FONT = _configured_or_fallback(
    "AIRCONTROL_BODY_FONT",
    "Inter",
    ("Segoe UI",),
)
