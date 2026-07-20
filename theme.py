import tkinter as tk
from tkinter import ttk

# ---- Color Palette (Forest theme) ----
BG_DARK = "#1b2e1f"      # deep forest green header banner
BG_LIGHT = "#eef2e6"     # soft sage background
CARD_BG = "#fbfbf6"      # warm off-white card background
BORDER = "#a8c3a1"       # muted sage border

ACCENT = "#3f6b4f"       # forest green (tabs, neutral highlights)
SUCCESS = "#6a994e"      # olive green (safe demos)
DANGER = "#bc4749"       # brick red (unsafe demos)
WARNING = "#dda15e"      # warm amber/tan

TEXT_LIGHT = "#f6fff8"
TEXT_DARK = "#1b2e1f"
TEXT_MUTED = "#5c6f5e"

FONT_TITLE = ("Segoe UI", 17, "bold")
FONT_SUBTITLE = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)


def apply_theme(root):
    root.configure(bg=BG_LIGHT)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure("TNotebook", background=BG_LIGHT, borderwidth=0)
    style.configure("TNotebook.Tab", font=FONT_HEADER, padding=(18, 10),
                     background=BORDER, foreground=TEXT_DARK)
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", TEXT_LIGHT)])

    style.configure("Safe.TButton", font=FONT_HEADER, padding=10,
                     background=SUCCESS, foreground=TEXT_LIGHT, borderwidth=0)
    style.map("Safe.TButton", background=[("active", "#557a3d"), ("disabled", "#bcd1a8")])

    style.configure("Unsafe.TButton", font=FONT_HEADER, padding=10,
                     background=DANGER, foreground=TEXT_LIGHT, borderwidth=0)
    style.map("Unsafe.TButton", background=[("active", "#9c3a3c"), ("disabled", "#e0b3b3")])

    return style


def build_header(root, subtitle):
    header = tk.Frame(root, bg=BG_DARK, height=64)
    header.pack(fill="x", side="top")
    header.pack_propagate(False)

    tk.Label(header, text="ConcurrencyLab", font=FONT_TITLE, bg=BG_DARK, fg=TEXT_LIGHT)\
        .pack(side="top", anchor="w", padx=20, pady=(8, 0))
    tk.Label(header, text=subtitle, font=FONT_SUBTITLE, bg=BG_DARK, fg="#a8c3a1")\
        .pack(side="top", anchor="w", padx=20)

    return header


def build_card(parent):
    outer = tk.Frame(parent, bg=BG_LIGHT)
    outer.pack(fill="both", expand=True, padx=16, pady=16)

    card = tk.Frame(outer, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True)
    return card