"""
GUI tab showing aggregated performance data as hand-drawn bar charts
using plain Tkinter Canvas - NO external charting library required.
Combined with the rest of the app (which only ever used tkinter,
sqlite3, and multiprocessing - all Python standard library), this
means the ENTIRE project now has zero pip-installable dependencies:
`python main.py` just works, on any machine with Python installed.
"""

import tkinter as tk
from tkinter import ttk

from logger import clear_all_runs
from stats import compute_stats
import theme

CHART_WIDTH = 600     # fixed pixel width every bar-chart panel is drawn at
CHART_GAP = 22          # vertical gap left between stacked chart panels


class StatsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self._build_ui()

    def _build_ui(self):
        # Same scrollable card every other tab uses - since this tab can
        # have up to 6 stacked charts, it can get tall, and the card's
        # own scrollbar handles that without needing a second, nested one.
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

        # The single Canvas ALL 6 bar charts get hand-drawn onto, stacked
        # vertically. Its height gets resized in refresh() to exactly
        # match however tall the drawn content actually is.
        self.canvas = tk.Canvas(card, width=CHART_WIDTH, bg=theme.CARD_BG, highlightthickness=0)
        self.canvas.pack(padx=16, pady=(6, 16))

        self.refresh()  # draw whatever data already exists as soon as the tab is built

    def _draw_bar_group(self, y_top, title, labels, values, colors, stagger=False):
        """
        Draws one bar-chart 'panel' onto self.canvas, starting at
        vertical position y_top. Returns the y-coordinate where the
        NEXT panel should start, so multiple charts stack automatically
        with no manual position bookkeeping needed outside this function.

        - Every bar gets its exact numeric value labeled directly above
          it, even when that value is 0 - so a correctly-zero "safe
          mode had no violations" result reads as a clear labeled zero,
          not just an invisible flat bar.
        - When stagger=True (only used for the 10-bar duration chart),
          x-axis labels alternate between two vertical rows, since 10
          labels side-by-side would otherwise run into each other.
        """
        title_h = 22                                  # space reserved for the title text
        label_rows_h = 46 if stagger else 30           # extra room if labels use 2 staggered rows
        plot_h = 120                                     # height of the actual bar-plotting area
        panel_h = title_h + plot_h + label_rows_h        # total height this one panel occupies

        # --- Title, centered at the top of this panel ---
        self.canvas.create_text(CHART_WIDTH / 2, y_top + title_h / 2, text=title,
                                 font=("Segoe UI", 10, "bold"), fill=theme.TEXT_DARK)

        # --- Bar geometry setup ---
        baseline_y = y_top + title_h + plot_h  # the "0" line every bar grows upward from
        n = len(values)
        slot_w = CHART_WIDTH / n                  # horizontal space allotted to each bar+label
        bar_w = slot_w * 0.5                        # actual bar width (leaves a visible gap between bars)

        max_value = max(values) if values else 0
        # Always leave SOME visible vertical scale, even when every
        # value is 0 - avoids a divide-by-zero and keeps the chart from
        # looking "broken" when all-zeros is the correct, expected result.
        scale_max = max(max_value * 1.3, 1)

        # --- Baseline axis line, spanning the full chart width ---
        self.canvas.create_line(0, baseline_y, CHART_WIDTH, baseline_y, fill=theme.BORDER, width=1)

        for i, (label, value, color) in enumerate(zip(labels, values, colors)):
            x_center = slot_w * i + slot_w / 2

            bar_h = (value / scale_max) * plot_h if scale_max > 0 else 0
            # Every bar gets a tiny minimum visible height (2px), even
            # at value=0, so the reader can see exactly WHERE that
            # (correctly zero) bar sits, instead of nothing being drawn.
            bar_h = max(bar_h, 2)

            self.canvas.create_rectangle(x_center - bar_w / 2, baseline_y - bar_h,
                                          x_center + bar_w / 2, baseline_y,
                                          fill=color, outline="")

            # Numeric value label, directly above its own bar
            self.canvas.create_text(x_center, baseline_y - bar_h - 10, text=str(value),
                                     font=("Segoe UI", 8), fill=theme.TEXT_DARK)

            # X-axis label below the bar. Staggering odd-indexed labels
            # onto a second, lower row prevents adjacent labels from
            # visually overlapping when there isn't enough horizontal
            # room to fit all 10 on one single row.
            if stagger and i % 2 == 1:
                label_y = baseline_y + 32
                # Small connector tick, since this label no longer sits
                # directly under its bar - keeps the association visible.
                self.canvas.create_line(x_center, baseline_y + 4, x_center, label_y - 8,
                                         fill=theme.TEXT_MUTED, width=1)
            else:
                label_y = baseline_y + 14

            self.canvas.create_text(x_center, label_y, text=label,
                                     font=("Segoe UI", 7), fill=theme.TEXT_MUTED)

        return y_top + panel_h + CHART_GAP  # tells the caller where the NEXT panel should start

    def refresh(self):
        """Recomputes stats from the database and redraws every chart from scratch."""
        stats = compute_stats()  # None if no runs have been logged yet

        self.canvas.delete("all")  # wipe everything before redrawing

        if stats is None:
            # No data yet - show a friendly placeholder instead of empty charts
            self.canvas.config(height=110)
            self.canvas.create_text(CHART_WIDTH / 2, 50,
                                     text="No data yet.\nRun some demos first!",
                                     font=("Segoe UI", 11), fill=theme.TEXT_MUTED, justify="center")
            return

        y = 10  # running vertical position; each _draw_bar_group() call advances it forward

        # --- Chart 1: average duration across all logged (demo_type, mode) combos ---
        # Uses stagger=True since up to 10 bars side-by-side need 2 label rows.
        duration_labels = [d["label"] for d in stats["duration_chart"]]
        duration_values = [d["value"] for d in stats["duration_chart"]]
        duration_colors = [theme.SUCCESS if d["is_safe"] else theme.DANGER
                            for d in stats["duration_chart"]]
        y = self._draw_bar_group(y, "Average Run Duration (seconds)",
                                  duration_labels, duration_values, duration_colors, stagger=True)

        # --- Charts 2-6: always exactly 2 bars (Safe vs Unsafe), so no stagger needed ---
        y = self._draw_bar_group(
            y, "Total Capacity Violations (Producer-Consumer)",
            ["Safe", "Unsafe"],
            [stats["pc_violations"].get("safe", 0), stats["pc_violations"].get("unsafe", 0)],
            [theme.SUCCESS, theme.DANGER]
        )

        y = self._draw_bar_group(
            y, "Deadlocks Detected (Dining Philosophers)",
            ["Safe", "Unsafe"],
            [stats["dp_deadlocks"].get("safe", 0), stats["dp_deadlocks"].get("unsafe", 0)],
            [theme.SUCCESS, theme.DANGER]
        )

        y = self._draw_bar_group(
            y, "Lost Updates (Multi-Process Counter)",
            ["Safe", "Unsafe"],
            [stats["mp_lost_updates"].get("safe", 0), stats["mp_lost_updates"].get("unsafe", 0)],
            [theme.SUCCESS, theme.DANGER]
        )

        y = self._draw_bar_group(
            y, "Overlap Violations (Readers-Writers)",
            ["Safe", "Unsafe"],
            [stats["rw_violations"].get("safe", 0), stats["rw_violations"].get("unsafe", 0)],
            [theme.SUCCESS, theme.DANGER]
        )

        y = self._draw_bar_group(
            y, "Cycles Found by Detector (Wait-For Graph)",
            ["Safe", "Unsafe"],
            [stats["dd_cycles"].get("safe", 0), stats["dd_cycles"].get("unsafe", 0)],
            [theme.SUCCESS, theme.DANGER]
        )

        # Resize the canvas widget itself to exactly match the total
        # height of everything just drawn, so the outer scrollable
        # card's scrollbar correctly reflects the true content height.
        self.canvas.config(height=y)

    def clear_data(self):
        """Wipes all logged data and redraws the (now-empty) charts."""
        clear_all_runs()
        self.refresh()