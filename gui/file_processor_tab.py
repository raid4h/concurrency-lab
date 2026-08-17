"""
GUI tab for the Thread Pool File Processor. Lets the user pick a REAL
folder on their computer via the native OS folder picker, then compares
hashing every file in it sequentially vs. with a thread pool, showing
the actual measured speedup - a genuinely practical, tangible demo,
not just an abstract simulation like the other tabs.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
import queue

from file_processor import list_files, process_sequential, process_thread_pool
from logger import log_run
import theme
from config import NUM_WORKERS


class FileProcessorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.folder_path = None        # set once the user picks a folder
        self.file_paths = []             # list of files found in that folder
        self.sequential_time = None        # filled in after a sequential run completes
        self.threadpool_time = None          # filled in after a thread-pool run completes
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_scrollable_card(self)

        tk.Label(card, text="Thread Pool: Parallel File Processor", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text="A practical application of concurrency: computes an MD5 checksum for "
                      "every file in a real folder you choose, once sequentially and once with "
                      "a thread pool - the same shared-queue pattern as Producer-Consumer, "
                      "applied to real disk I/O. Shows the genuine speedup threading provides.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # --- Folder picker row ---
        picker_frame = tk.Frame(card, bg=theme.CARD_BG)
        picker_frame.pack(pady=6)

        self.choose_btn = ttk.Button(picker_frame, text="Choose Folder...",
                                      style="Safe.TButton", command=self.choose_folder)
        self.choose_btn.grid(row=0, column=0, padx=6)

        self.folder_label = tk.Label(picker_frame, text="No folder selected.",
                                      font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)
        self.folder_label.grid(row=0, column=1, padx=6)

        # --- Run buttons row ---
        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        # NOTE: color choice here is different from other tabs. Red/green
        # elsewhere means "buggy vs correct" - here neither run is a bug,
        # so red just marks the baseline and green marks the improved
        # (thread pool) approach being highlighted, for visual consistency.
        self.seq_btn = ttk.Button(button_frame, text="Run Sequential", style="Unsafe.TButton",
                                   command=self.run_sequential, state="disabled")
        self.seq_btn.grid(row=0, column=0, padx=6)

        self.pool_btn = ttk.Button(button_frame, text=f"Run Thread Pool ({NUM_WORKERS} workers)",
                                    style="Safe.TButton", command=self.run_thread_pool, state="disabled")
        self.pool_btn.grid(row=0, column=1, padx=6)

        self.status_label = tk.Label(card, text="Pick a folder to begin.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=6)

        # --- Speedup readout, shown once both runs have completed ---
        self.result_label = tk.Label(card, text="", font=("Segoe UI", 11, "bold"),
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.result_label.pack(pady=4)

        # --- Small hand-drawn comparison chart: 2 bars, sequential vs thread pool ---
        self.chart_canvas = tk.Canvas(card, width=400, height=140, bg=theme.CARD_BG, highlightthickness=0)
        self.chart_canvas.pack(pady=6)

        # --- Log/terminal area ---
        self.log_area = scrolledtext.ScrolledText(card, width=76, height=10, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(6, 16), padx=16)

    def log(self, message):
        """Appends a line of text to the terminal box."""
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def choose_folder(self):
        """
        Opens the native OS folder picker. filedialog is part of
        Python's standard library (bundled with tkinter) - no extra
        install needed, keeping the whole project dependency-free.
        """
        chosen = filedialog.askdirectory(title="Select a folder to process")
        if not chosen:
            return  # user cancelled the dialog - do nothing

        self.folder_path = chosen
        self.file_paths = list_files(chosen)

        # A newly chosen folder means any previous comparison no longer applies
        self.sequential_time = None
        self.threadpool_time = None
        self.result_label.config(text="")
        self.chart_canvas.delete("all")
        self._clear_log()

        if not self.file_paths:
            self.folder_label.config(text=f"{chosen}  (no files found)")
            self.status_label.config(text="This folder has no files to process. Pick another one.",
                                      fg=theme.DANGER)
            self.seq_btn.config(state="disabled")
            self.pool_btn.config(state="disabled")
            return

        self.folder_label.config(text=f"{chosen}  ({len(self.file_paths)} files)")
        self.status_label.config(text="Ready to process.", fg=theme.TEXT_DARK)
        self.seq_btn.config(state="normal")
        self.pool_btn.config(state="normal")

    def _draw_comparison_chart(self):
        """
        Draws a simple 2-bar comparison once BOTH run times are known.
        Same hand-drawn Canvas technique as the Performance Stats tab -
        no external charting library used anywhere in this project.
        """
        self.chart_canvas.delete("all")

        if self.sequential_time is None or self.threadpool_time is None:
            return  # need both results before a comparison makes sense

        values = [self.sequential_time, self.threadpool_time]
        labels = ["Sequential", f"Thread Pool ({NUM_WORKERS})"]
        colors = [theme.DANGER, theme.SUCCESS]

        max_value = max(values)
        scale_max = max(max_value * 1.3, 0.1)  # avoid a divide-by-zero on very fast runs

        plot_h = 90
        baseline_y = 110
        slot_w = 400 / 2
        bar_w = slot_w * 0.5

        self.chart_canvas.create_line(0, baseline_y, 400, baseline_y, fill=theme.BORDER, width=1)

        for i, (label, value, color) in enumerate(zip(labels, values, colors)):
            x_center = slot_w * i + slot_w / 2
            bar_h = max((value / scale_max) * plot_h, 2)  # minimum 2px so even tiny bars are visible

            self.chart_canvas.create_rectangle(x_center - bar_w / 2, baseline_y - bar_h,
                                                x_center + bar_w / 2, baseline_y,
                                                fill=color, outline="")
            self.chart_canvas.create_text(x_center, baseline_y - bar_h - 12,
                                           text=f"{value:.3f}s", font=("Segoe UI", 9, "bold"),
                                           fill=theme.TEXT_DARK)
            self.chart_canvas.create_text(x_center, baseline_y + 16, text=label,
                                           font=("Segoe UI", 8), fill=theme.TEXT_MUTED)

    def poll_queue(self):
        """Runs every 50ms: checks for new events from background threads."""
        try:
            while True:
                event = self.event_queue.get_nowait()

                if event == "DONE":
                    self.running = False
                    self.seq_btn.config(state="normal")
                    self.pool_btn.config(state="normal")
                    continue

                if event["type"] == "file_progress":
                    mode = event["mode"]
                    self.status_label.config(
                        text=f"[{mode}] Hashed {event['index'] + 1}/{event['total']}: {event['filename']}",
                        fg=theme.TEXT_DARK
                    )

                elif event["type"] == "file_done":
                    mode = event["mode"]
                    duration = event["duration"]

                    # Log this run's timing to the same shared database used
                    # by every other tab, for consistency across the app.
                    log_run("file_processor", mode, duration, violation_count=0)

                    if mode == "sequential":
                        self.sequential_time = duration
                        self.log(f">>> Sequential run finished: {duration:.3f}s "
                                 f"for {len(self.file_paths)} files.")
                    else:
                        self.threadpool_time = duration
                        self.log(f">>> Thread Pool run finished: {duration:.3f}s "
                                 f"for {len(self.file_paths)} files using {NUM_WORKERS} workers.")

                    self._draw_comparison_chart()

                    # Once BOTH times are known, compute and display the speedup
                    if self.sequential_time is not None and self.threadpool_time is not None:
                        if self.threadpool_time > 0:
                            speedup = self.sequential_time / self.threadpool_time
                            self.result_label.config(
                                text=f"Thread pool was {speedup:.2f}x faster than sequential.",
                                fg=theme.SUCCESS
                            )
                            self.log(f">>> Speedup: {speedup:.2f}x. Both results logged to database.")

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def run_sequential(self):
        self._run(mode="sequential")

    def run_thread_pool(self):
        self._run(mode="threadpool")

    def _run(self, mode):
        if self.running or not self.file_paths:
            return

        self.running = True
        self.seq_btn.config(state="disabled")
        self.pool_btn.config(state="disabled")
        self.status_label.config(text=f"Running {mode}...", fg=theme.TEXT_DARK)

        def worker():
            if mode == "sequential":
                process_sequential(self.file_paths, self.event_queue)
            else:
                process_thread_pool(self.file_paths, NUM_WORKERS, self.event_queue)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()