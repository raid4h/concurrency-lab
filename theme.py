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
    """Configures ttk widget styles (tabs, buttons) to use the forest palette."""
    root.configure(bg=BG_LIGHT)
    style = ttk.Style(root)
    style.theme_use("clam")  # 'clam' is required for real color customization on Windows

    style.configure("TNotebook", background=BG_LIGHT, borderwidth=0)
    style.configure("TNotebook.Tab", font=FONT_HEADER, padding=(18, 10),
                     background=BORDER, foreground=TEXT_DARK)
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", TEXT_LIGHT)])

    # cursor="hand2" here applies to EVERY button in the app that uses
    # this style - since every ttk.Button across all 7 tabs is created
    # with style="Safe.TButton" or style="Unsafe.TButton", this one
    # change is enough to add a hand cursor everywhere, with no need
    # to edit each individual button in each tab file.
    style.configure("Safe.TButton", font=FONT_HEADER, padding=10,
                     background=SUCCESS, foreground=TEXT_LIGHT, borderwidth=0,
                     cursor="hand2")
    style.map("Safe.TButton", background=[("active", "#557a3d"), ("disabled", "#bcd1a8")])

    style.configure("Unsafe.TButton", font=FONT_HEADER, padding=10,
                     background=DANGER, foreground=TEXT_LIGHT, borderwidth=0,
                     cursor="hand2")
    style.map("Unsafe.TButton", background=[("active", "#9c3a3c"), ("disabled", "#e0b3b3")])

    return style


def build_header(root, subtitle):
    """Creates the dark title banner at the top of the window."""
    header = tk.Frame(root, bg=BG_DARK, height=64)
    header.pack(fill="x", side="top")
    header.pack_propagate(False)  # stops the header from shrinking to fit its children

    tk.Label(header, text="ConcurrencyLab", font=FONT_TITLE, bg=BG_DARK, fg=TEXT_LIGHT)\
        .pack(side="top", anchor="w", padx=20, pady=(8, 0))
    tk.Label(header, text=subtitle, font=FONT_SUBTITLE, bg=BG_DARK, fg="#a8c3a1")\
        .pack(side="top", anchor="w", padx=20)

    return header


def build_card(parent):
    """
    A plain, NON-scrolling white 'card' container. Kept for reference,
    but build_scrollable_card() below should be used for all real tabs.
    """
    outer = tk.Frame(parent, bg=BG_LIGHT)
    outer.pack(fill="both", expand=True, padx=16, pady=16)

    card = tk.Frame(outer, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="both", expand=True)
    return card


def build_scrollable_card(parent):
    """
    Like build_card(), but wraps the white 'card' inside a scrollable
    Tkinter Canvas + Scrollbar, so a tab's content can be taller than
    the visible window without anything getting clipped off.
    """
    outer = tk.Frame(parent, bg=BG_LIGHT)
    outer.pack(fill="both", expand=True, padx=16, pady=16)

    scroll_canvas = tk.Canvas(outer, bg=BG_LIGHT, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=scroll_canvas.yview)

    card = tk.Frame(scroll_canvas, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
    card_window_id = scroll_canvas.create_window((0, 0), window=card, anchor="nw")

    def _update_scrollregion(event):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

    card.bind("<Configure>", _update_scrollregion)

    def _match_card_width(event):
        scroll_canvas.itemconfig(card_window_id, width=event.width)

    scroll_canvas.bind("<Configure>", _match_card_width)

    scroll_canvas.configure(yscrollcommand=scrollbar.set)
    scroll_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_enter(event):
        scroll_canvas.bind_all(
            "<MouseWheel>",
            lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )

    def _on_leave(event):
        scroll_canvas.unbind_all("<MouseWheel>")

    scroll_canvas.bind("<Enter>", _on_enter)
    scroll_canvas.bind("<Leave>", _on_leave)

    return card


def build_legend(parent, items, columns=3):
    """
    Builds a small legend made of real colored SWATCHES next to their
    descriptions, instead of describing colors by name in plain text
    (e.g. the old "Brown = has 1 fork"). A viewer sees the EXACT color
    being referenced, which is clearer and looks more polished.

    'items' is a list of (color_hex, label_text) tuples. Items wrap
    onto multiple rows automatically once 'columns' is exceeded, so
    legends with more entries (like Dining Philosophers' 5 states)
    don't run off the edge of the card.
    """
    legend_frame = tk.Frame(parent, bg=CARD_BG)

    for i, (color, label_text) in enumerate(items):
        row = i // columns   # integer division: which row this item lands on
        col = i % columns     # remainder: which column within that row

        # One small container per legend entry, so its swatch and text
        # stay visually grouped together as a single unit.
        entry = tk.Frame(legend_frame, bg=CARD_BG)
        entry.grid(row=row, column=col, padx=8, pady=2, sticky="w")

        # The colored square itself. A tiny Canvas is used (rather than
        # a colored Label background) because Canvas lets us draw a
        # crisp square WITH a thin border, which reads more clearly as
        # an intentional "swatch" than a borderless colored rectangle.
        swatch = tk.Canvas(entry, width=12, height=12, highlightthickness=0, bg=CARD_BG)
        swatch.create_rectangle(1, 1, 12, 12, fill=color, outline=BORDER)
        swatch.pack(side="left", padx=(0, 5))

        tk.Label(entry, text=label_text, font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED)\
            .pack(side="left")

    return legend_frame