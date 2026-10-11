"""
AirControl — Japanese Minimal × Swiss Engineering Design System
Palette, Typography scale, and Visual Tokens.
"""

from ui.fonts import BODY_FONT, DISPLAY_FONT

# Restrained Japanese Minimal × Swiss Engineering Palette
COLOR_IVORY = "#F2EFE7"         # Warm Ivory: Light surfaces, borders & primary highlights
COLOR_CHARCOAL = "#20211F"      # Charcoal Ink: Deep structural surfaces & primary ink
COLOR_PANEL_DARK = "#181918"    # Recessed instrument background
COLOR_PANEL_SURFACE = "#252724" # Raised cards and control surfaces
COLOR_PANEL_BORDER = "#3A3D38"  # Subtle structural dividers
COLOR_INDIGO = "#273449"        # Deep Indigo: Technical sections & badges
COLOR_VERMILION = "#C74735"     # Vermilion Red: Primary action, recording & critical focus
COLOR_VERMILION_HOVER = "#B33E2E"
COLOR_STONE = "#B9B5AA"         # Muted Stone: Secondary labels, metadata & borders
COLOR_SAGE = "#7C8B78"          # Soft Sage: Restrained success states
COLOR_ACCENT_BG = "#2E332D"     # Active button / selected pill background

# Neue Haas Grotesk when installed/configured; otherwise bundled Space Grotesk,
# then Segoe UI. Body text prefers Inter and falls back to Segoe UI.
FONT_DISPLAY = DISPLAY_FONT
FONT_BODY = BODY_FONT
FONT_SANS = FONT_BODY
FONT_SERIF = FONT_DISPLAY  # Backward-compatible token for existing UI consumers.
FONT_MONO = "Consolas"          # Precision technical readout & telemetry
