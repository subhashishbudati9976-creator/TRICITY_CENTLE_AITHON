"""
AirControl — Japanese Minimal × Swiss Engineering Control Center
Precision instrument interface components for CustomTkinter.
"""

import time
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from ui.theme import (
    COLOR_CHARCOAL,
    COLOR_INDIGO,
    COLOR_IVORY,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_DARK,
    COLOR_PANEL_SURFACE,
    COLOR_SAGE,
    COLOR_STONE,
    COLOR_VERMILION,
    COLOR_VERMILION_HOVER,
    FONT_MONO,
    FONT_SANS,
    FONT_SERIF,
)


class SectionHeader(ctk.CTkFrame):
    """Small numbered section label inspired by precision Japanese instrumentation."""

    def __init__(self, master, number: str, title: str, status_text: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        tag = ctk.CTkLabel(
            self,
            text=f"[ {number} ]",
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_VERMILION,
        )
        tag.grid(row=0, column=0, sticky="w", padx=(0, 8))

        heading = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ctk.CTkFont(family=FONT_SANS, size=12, weight="bold"),
            text_color=COLOR_IVORY,
        )
        heading.grid(row=0, column=1, sticky="w")

        if status_text:
            self.status_label = ctk.CTkLabel(
                self,
                text=status_text,
                font=ctk.CTkFont(family=FONT_MONO, size=10),
                text_color=COLOR_STONE,
            )
            self.status_label.grid(row=0, column=2, sticky="e")
        else:
            self.status_label = None


class TelemetryLog(ctk.CTkFrame):
    """Chronological instrument readout / audit ledger with monospaced telemetry entries."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL_DARK,
            border_color=COLOR_PANEL_BORDER,
            border_width=1,
            corner_radius=4,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header sub-bar
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=10, pady=(6, 2), sticky="ew")
        ctk.CTkLabel(
            hdr,
            text="TIMESTAMP   SOURCE   TELEMETRY EVENT                      STATUS",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=COLOR_STONE,
        ).pack(side="left")

        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            fg_color=COLOR_PANEL_DARK,
            text_color=COLOR_IVORY,
            activate_scrollbars=True,
            wrap="none",
        )
        self.textbox.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.textbox.configure(state="disabled")

        self.append_entry("SYS", "AirControl Engine Initialized", "ONLINE")

    def append_entry(self, source: str, event: str, status: str = "OK"):
        now_str = time.strftime("%H:%M:%S")
        entry_line = f"[{now_str}]  [{source:<6}]  {event:<38}  [{status}]\n"

        self.textbox.configure(state="normal")
        self.textbox.insert("end", entry_line)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class ValueSlider(ctk.CTkFrame):
    """Precision slider with live numerical readout."""

    def __init__(
        self,
        master,
        label: str,
        from_: float,
        to: float,
        default: float,
        unit: str = "",
        on_change: Optional[Callable[[float], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.unit = unit
        self.on_change = on_change
        self.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=FONT_SANS, size=11),
            text_color=COLOR_STONE,
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.val_label = ctk.CTkLabel(
            self,
            text=f"{default:.2f} {unit}".strip(),
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            text_color=COLOR_IVORY,
        )
        self.val_label.grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.slider = ctk.CTkSlider(
            self,
            from_=from_,
            to=to,
            number_of_steps=40,
            command=self._handle_change,
            button_color=COLOR_STONE,
            button_hover_color=COLOR_IVORY,
            progress_color=COLOR_INDIGO,
            fg_color=COLOR_PANEL_DARK,
            height=14,
        )
        self.slider.set(default)
        self.slider.grid(row=0, column=1, sticky="ew", padx=8)

    def _handle_change(self, value: float):
        self.val_label.configure(text=f"{value:.2f} {self.unit}".strip())
        if self.on_change:
            self.on_change(value)
