"""
GUI tab for the real-data, three-strategy word-count benchmark. Kept
deliberately simple and functional (single-column layout, no fancy
diagram placement) since the point here is measurable optimization on
real data, not visual polish.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import threading
import queue

from word_count_benchmark import list_text_files, run_sequential, run_thread_pool, run_multiprocess
from logger import log_run
import theme
from config import NUM_WORKERS  # reused from file_processor's existing worker-count constant


class WordCountTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.folder_path = None
        self.file_paths = []
        # Stores each strategy's measured duration once it completes,
        # so the comparison chart can be drawn once all three are known.
        self.results = {"sequential": None, "threadpool": None, "multiprocess": None}
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_scrollable_card(self)

        tk.Label(card, text="Real-Data Benchmark: Parallel Word Count", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text="Counts word frequencies across every text file in a real folder you "
                      "choose, three ways: sequential, a thread pool, and real OS processes. "
                      "Uses mmap() to memory-map files and multiprocessing.Pipe() (a direct "
                      "OS pipe wrapper) for inter-process results - real system calls, real "
                      "data, real measured performance.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=620, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # --- Folder picker ---
        picker_frame = tk.Frame(card, bg=theme.CARD_BG)
        picker_frame.pack(pady=6)

        self.choose_btn = ttk.Button(picker_frame, text="Choose Folder...",
                                      style="Safe.TButton", command=self.choose_folder)
        self.choose_btn.grid(row=0, column=0, padx=6)

        self.folder_label = tk.Label(picker_frame, text="No folder selected.",
                                      font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)
        self.folder_label.grid(row=0, column=1, padx=6)

        # --- Three run buttons, one per strategy ---
        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.seq_btn = ttk.Button(button_frame, text="Run Sequential",
                                   style="Unsafe.TButton", command=self.run_sequential,
                                   state="disabled")
        self.seq_btn.grid(row=0, column=0, padx=5)

        self.thread_btn = ttk.Button(button_frame, text=f"Run Thread Pool ({NUM_WORKERS})",
                                      style="Safe.TButton", command=self.run_threadpool,
                                      state="disabled")
        self.thread_btn.grid(row=0, column=1, padx=5)

        self.proc_btn = ttk.Button(button_frame, text=f"Run Multiprocess ({NUM_WORKERS})",
                                    style="Safe.TButton", command=self.run_multiprocess,
                                    state="disabled")
        self.proc_btn.grid(row=0, column=2, padx=5)

        self.status_label = tk.Label(card, text="Pick a folder to begin.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=6)

        # --- Insight readout, filled in once all three strategies have run ---
        self.insight_label = tk.Label(card, text="", font=("Segoe UI", 10, "bold"),
                                       bg=theme.CARD_BG, fg=theme.TEXT_DARK,
                                       wraplength=620, justify="left")
        self.insight_label.pack(pady=4, padx=16)

        # --- Hand-drawn 3-bar comparison chart ---
        self.chart_canvas = tk.Canvas(card, width=480, height=150, bg=theme.CARD_BG, highlightthickness=0)
        self.chart_canvas.pack(pady=6)

        # --- Terminal / log area ---
        self.log_area = scrolledtext.ScrolledText(card, width=80, height=12, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(6, 16), padx=16)

    def log(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def choose_folder(self):
        """Opens the native OS folder picker (part of tkinter - no extra install needed)."""
        chosen = filedialog.askdirectory(title="Select a folder of text files to benchmark")
        if not chosen:
            return

        self.folder_path = chosen
        self.file_paths = list_text_files(chosen)

        # A newly chosen folder invalidates any previous comparison
        self.results = {"sequential": None, "threadpool": None, "multiprocess": None}
        self.insight_label.config(text="")
        self.chart_canvas.delete("all")
        self._clear_log()

        if not self.file_paths:
            self.folder_label.config(text=f"{chosen}  (no matching text files found)")
            self.status_label.config(text="Pick a folder containing .txt/.py/.md/.csv/.log files.",
                                      fg=theme.DANGER)
            self.seq_btn.config(state="disabled")
            self.thread_btn.config(state="disabled")
            self.proc_btn.config(state="disabled")
            return

        self.folder_label.config(text=f"{chosen}  ({len(self.file_paths)} files)")
        self.status_label.config(text="Ready to benchmark.", fg=theme.TEXT_DARK)
        self.seq_btn.config(state="normal")
        self.thread_btn.config(state="normal")
        self.proc_btn.config(state="normal")

    def _draw_comparison_chart(self):
        """Hand-drawn 3-bar chart comparing whichever strategies have completed so far."""
        self.chart_canvas.delete("all")

        labels_order = [("sequential", "Sequential"), ("threadpool", f"Threads ({NUM_WORKERS})"),
                         ("multiprocess", f"Processes ({NUM_WORKERS})")]
        known = [(label, self.results[key]) for key, label in labels_order if self.results[key] is not None]

        if not known:
            return

        values = [v for _, v in known]
        max_value = max(values)
        scale_max = max(max_value * 1.3, 0.05)

        plot_h = 100
        baseline_y = 120
        slot_w = 480 / len(known)
        bar_w = slot_w * 0.5

        # Sequential = red (baseline), the two optimized strategies = green,
        # matching the safe/unsafe color language used throughout the app.
        colors = {"Sequential": theme.DANGER}

        self.chart_canvas.create_line(0, baseline_y, 480, baseline_y, fill=theme.BORDER, width=1)

        for i, (label, value) in enumerate(known):
            x_center = slot_w * i + slot_w / 2
            color = colors.get(label, theme.SUCCESS)
            bar_h = max((value / scale_max) * plot_h, 2)

            self.chart_canvas.create_rectangle(x_center - bar_w / 2, baseline_y - bar_h,
                                                x_center + bar_w / 2, baseline_y,
                                                fill=color, outline="")
            self.chart_canvas.create_text(x_center, baseline_y - bar_h - 12,
                                           text=f"{value:.3f}s", font=("Segoe UI", 9, "bold"),
                                           fill=theme.TEXT_DARK)
            self.chart_canvas.create_text(x_center, baseline_y + 16, text=label,
                                           font=("Segoe UI", 8), fill=theme.TEXT_MUTED)

    def _update_insight(self):
        """Once all three results are in, compute speedups and explain the GIL insight."""
        seq = self.results["sequential"]
        th = self.results["threadpool"]
        mp = self.results["multiprocess"]

        if seq is None or th is None or mp is None:
            return  # need all three before drawing a conclusion

        thread_speedup = seq / th if th > 0 else 0
        process_speedup = seq / mp if mp > 0 else 0

        self.insight_label.config(
            text=(f"Thread pool speedup: {thread_speedup:.2f}x   |   "
                  f"Multiprocess speedup: {process_speedup:.2f}x\n"
                  f"This is CPU-bound counting work: threads are limited by Python's GIL "
                  f"(only one runs Python bytecode at a time), while separate processes each "
                  f"get their own interpreter and GIL - real parallelism, not just concurrency."),
            fg=theme.SUCCESS if process_speedup > thread_speedup else theme.TEXT_DARK
        )

    def poll_queue(self):
        try:
            while True:
                event = self.event_queue.get_nowait()

                if event == "DONE":
                    self.running = False
                    self.seq_btn.config(state="normal")
                    self.thread_btn.config(state="normal")
                    self.proc_btn.config(state="normal")
                    continue

                if event["type"] == "progress":
                    self.status_label.config(
                        text=f"[{event['mode']}] {event['index'] + 1}/{event['total']}: {event['filename']}",
                        fg=theme.TEXT_DARK
                    )

                elif event["type"] == "strategy_done":
                    mode = event["mode"]
                    duration = event["duration"]
                    total_words = event["total_words"]
                    words_list = ", ".join(f"{w}({n})" for w, n in event["top_words"])

                    self.results[mode] = duration
                    log_run("word_count_benchmark", mode, duration, violation_count=0)

                    self.log(f">>> [{mode}] finished in {duration:.3f}s | "
                             f"{total_words} words counted | top words: {words_list}")

                    self._draw_comparison_chart()
                    self._update_insight()

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def run_sequential(self):
        self._run("sequential")

    def run_threadpool(self):
        self._run("threadpool")

    def run_multiprocess(self):
        self._run("multiprocess")

    def _run(self, mode):
        if self.running or not self.file_paths:
            return

        self.running = True
        self.seq_btn.config(state="disabled")
        self.thread_btn.config(state="disabled")
        self.proc_btn.config(state="disabled")
        self.status_label.config(text=f"Running {mode}...", fg=theme.TEXT_DARK)

        def worker():
            if mode == "sequential":
                run_sequential(self.file_paths, self.event_queue)
            elif mode == "threadpool":
                run_thread_pool(self.file_paths, NUM_WORKERS, self.event_queue)
            else:
                run_multiprocess(self.file_paths, NUM_WORKERS, self.event_queue)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()