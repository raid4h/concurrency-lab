"""
GUI tab showing aggregated performance charts, built from every logged
demo run in the SQLite database.
"""

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from logger import clear_all_runs
from stats import build_stats_figure
import theme


class StatsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.canvas_widget = None  # holds the embedded matplotlib widget once drawn
        self._build_ui()

    def _build_ui(self):
        # Scrollable card: the chart is tall (6 stacked subplots), so this
        # lets the user scroll down to see all of it at proper size.
        card = theme.build_scrollable_card(self)

        tk.Label(card, text="Performance Statistics", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card, text="Aggregated data from every demo run logged to the database so far. "
                             "Scroll down to see all charts.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)\
            .pack(anchor="w", padx=16, pady=(0, 10))

        btn_frame = tk.Frame(card, bg=theme.CARD_BG)
        btn_frame.pack(pady=6)

        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Stats", style="Safe.TButton",
                                       command=self.refresh)
        self.refresh_btn.grid(row=0, column=0, padx=5)

        self.clear_btn = ttk.Button(btn_frame, text="Clear All Data", style="Unsafe.TButton",
                                     command=self.clear_data)
        self.clear_btn.grid(row=0, column=1, padx=5)

        # Plain frame to hold the chart - deliberately NOT using fill/expand,
        # so the chart renders at its natural, correctly-spaced pixel size
        # instead of being stretched/squished to match window size.
        self.chart_frame = tk.Frame(card, bg=theme.CARD_BG)
        self.chart_frame.pack(padx=16, pady=(6, 16))

        self.refresh()

    def refresh(self):
        """Rebuilds the chart from the latest database contents."""
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()  # remove the old chart first

        fig = build_stats_figure()
        self.canvas_widget = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas_widget.draw()

        # IMPORTANT: no fill="both", expand=True here. Packing "naked" like
        # this keeps the widget at the figure's true pixel size (matching
        # its figsize * dpi), which is what avoids the squished/overlapping
        # text you saw before.
        self.canvas_widget.get_tk_widget().pack()

    def clear_data(self):
        """Wipes all logged data and refreshes the (now-empty) chart."""
        clear_all_runs()
        self.refresh()