import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time
import multiprocessing

from multiproc_worker import run_multiprocess_demo
from logger import log_run
import theme
from config import NUM_PROCESSES, INCREMENTS_PER_PROCESS


class ProcessTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.start_time = None
        self.current_mode = None
        self.process_states = {i: "waiting" for i in range(NUM_PROCESSES)}
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_card(self)

        tk.Label(card, text="Multi-Process Shared Counter", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text=f"{NUM_PROCESSES} separate OS processes each increment a shared counter "
                      f"{INCREMENTS_PER_PROCESS} times. Unlike threads, processes don't share memory "
                      f"automatically — this uses real inter-process shared memory and locking.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe Demo (With Lock)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe Demo (No Lock)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        self.canvas = tk.Canvas(card, width=560, height=110, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack(pady=10, padx=16)

        self.counter_label = tk.Label(card, text="Shared Counter: 0", font=("Segoe UI", 14, "bold"),
                                       bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.counter_label.pack(pady=4)

        self.result_label = tk.Label(card, text="", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.result_label.pack(pady=4)

        self.log_area = scrolledtext.ScrolledText(card, width=70, height=9, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(10, 16), padx=16)

        self.draw_processes()

    def log(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def draw_processes(self):
        self.canvas.delete("all")
        box_size = 70
        gap = 20
        start_x = 30

        for i in range(NUM_PROCESSES):
            x = start_x + i * (box_size + gap)
            state = self.process_states.get(i, "waiting")
            if state == "finished":
                color = theme.SUCCESS
            elif state == "running":
                color = theme.WARNING
            else:
                color = theme.BORDER

            self.canvas.create_oval(x, 15, x + box_size, 15 + box_size, fill=color, outline="white", width=2)
            self.canvas.create_text(x + box_size / 2, 15 + box_size / 2, text=f"P{i}",
                                     font=("Segoe UI", 12, "bold"), fill="white")

    def poll_queue(self):
        try:
            while True:
                event = self.event_queue.get_nowait()

                if event == "DONE":
                    self.running = False
                    self.safe_btn.config(state="normal")
                    self.unsafe_btn.config(state="normal")
                    self.log(">>> Demo finished.\n")
                    continue

                if event["type"] == "process_progress":
                    pid = event["id"]
                    self.process_states[pid] = "running"
                    self.draw_processes()
                    self.counter_label.config(text=f"Shared Counter: {event['counter']}")

                elif event["type"] == "process_finished":
                    pid = event["id"]
                    self.process_states[pid] = "finished"
                    self.draw_processes()
                    self.log(f"Process {pid} finished.")

                elif event["type"] == "process_done":
                    expected = event["expected"]
                    actual = event["actual"]
                    lost = event["lost_updates"]
                    duration = time.time() - self.start_time

                    log_run("multiprocess_counter", self.current_mode, duration, violation_count=lost)

                    if lost == 0:
                        self.result_label.config(
                            text=f"✓ Correct! Expected: {expected}   Actual: {actual}",
                            fg=theme.SUCCESS)
                        self.log(f"Result: counter is correct ({actual}/{expected}). No lost updates.")
                    else:
                        self.result_label.config(
                            text=f"✗ Lost updates! Expected: {expected}   Actual: {actual}   Lost: {lost}",
                            fg=theme.DANGER)
                        self.log(f"Result: {lost} increments were LOST due to unsynchronized "
                                 f"access across processes ({actual}/{expected}).")

                    self.log(f">>> Total time: {duration:.2f}s. Logged to database.")

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def run_safe_demo(self):
        self._run(use_lock=True)

    def run_unsafe_demo(self):
        self._run(use_lock=False)

    def _run(self, use_lock):
        if self.running:
            return
        self.running = True
        self.current_mode = "safe" if use_lock else "unsafe"
        self.start_time = time.time()
        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()
        self.process_states = {i: "waiting" for i in range(NUM_PROCESSES)}
        self.draw_processes()
        self.counter_label.config(text="Shared Counter: 0")
        self.result_label.config(text="")
        mode_text = "SAFE (multiprocessing.Lock)" if use_lock else "UNSAFE (no lock)"
        self.log(f">>> Starting {mode_text} demo across {NUM_PROCESSES} real OS processes...")

        def worker():
            mp_queue = multiprocessing.Queue()
            stop_forwarding = threading.Event()

            def forward():
                while not stop_forwarding.is_set() or not mp_queue.empty():
                    try:
                        item = mp_queue.get(timeout=0.1)
                        self.event_queue.put(item)
                    except queue.Empty:
                        continue

            forwarder_thread = threading.Thread(target=forward, daemon=True)
            forwarder_thread.start()

            run_multiprocess_demo(NUM_PROCESSES, INCREMENTS_PER_PROCESS, use_lock, mp_queue)

            stop_forwarding.set()
            forwarder_thread.join(timeout=2)

            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()