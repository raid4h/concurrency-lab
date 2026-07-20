import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from logger import clear_all_runs
from stats import build_stats_figure
import theme


class StatsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.canvas_widget = None
        self._build_ui()

    def _build_ui(self):
        card = theme.build_card(self)

        tk.Label(card, text="Performance Statistics", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card, text="Aggregated data from every demo run logged to the database so far.",
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

        self.chart_frame = tk.Frame(card, bg=theme.CARD_BG)
        self.chart_frame.pack(fill="both", expand=True, padx=16, pady=(6, 16))

        self.refresh()

    def refresh(self):
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()

        fig = build_stats_figure()
        self.canvas_widget = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas_widget.draw()
        self.canvas_widget.get_tk_widget().pack(fill="both", expand=True)

    def clear_data(self):
        clear_all_runs()
        self.refresh()