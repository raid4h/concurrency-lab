import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time

from readers_writers import run_readers_writers
from logger import log_run
import theme
from config import NUM_READERS, NUM_WRITERS, RW_ITERATIONS


class ReadersWritersTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.start_time = None
        self.current_mode = None
        self.reader_states = {i: "idle" for i in range(NUM_READERS)}
        self.writer_states = {i: "idle" for i in range(NUM_WRITERS)}
        self.document_version = 0
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_card(self)

        tk.Label(card, text="Readers-Writers Problem", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text=f"{NUM_READERS} readers and {NUM_WRITERS} writers share one document. "
                      f"Readers may overlap each other, but writers need exclusive access. "
                      f"Uses threading.Semaphore.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe Demo (Semaphores)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe Demo (No Locking)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        self.canvas = tk.Canvas(card, width=560, height=180, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack(pady=10, padx=16)

        legend = tk.Label(card,
                           text="Grey = idle    Green = reading    Amber = writing    Red = overlap violation",
                           font=("Segoe UI", 8), bg=theme.CARD_BG, fg=theme.TEXT_MUTED)
        legend.pack(pady=(0, 6))

        self.result_label = tk.Label(card, text="", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.result_label.pack(pady=4)

        self.log_area = scrolledtext.ScrolledText(card, width=70, height=12, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(6, 16), padx=16)

        self.draw_state()

    def log(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def _color_for(self, state):
        if state == "reading":
            return theme.ACCENT
        if state == "writing":
            return theme.WARNING
        if state == "violation":
            return theme.DANGER
        return theme.BORDER

    def draw_state(self):
        self.canvas.delete("all")
        box_size = 55
        gap = 15

        y_readers = 20
        start_x = 20
        for i in range(NUM_READERS):
            x = start_x + i * (box_size + gap)
            color = self._color_for(self.reader_states.get(i, "idle"))
            self.canvas.create_rectangle(x, y_readers, x + box_size, y_readers + box_size,
                                          fill=color, outline="white", width=2)
            self.canvas.create_text(x + box_size / 2, y_readers + box_size / 2, text=f"R{i}",
                                     fill="white", font=("Segoe UI", 11, "bold"))

        y_writers = y_readers + box_size + 30
        for i in range(NUM_WRITERS):
            x = start_x + i * (box_size + gap)
            color = self._color_for(self.writer_states.get(i, "idle"))
            self.canvas.create_rectangle(x, y_writers, x + box_size, y_writers + box_size,
                                          fill=color, outline="white", width=2)
            self.canvas.create_text(x + box_size / 2, y_writers + box_size / 2, text=f"W{i}",
                                     fill="white", font=("Segoe UI", 11, "bold"))

        doc_x = 380
        doc_y = 20
        doc_w = 160
        doc_h = (y_writers + box_size) - doc_y
        self.canvas.create_rectangle(doc_x, doc_y, doc_x + doc_w, doc_y + doc_h,
                                      outline=theme.BORDER, width=2, fill=theme.CARD_BG)
        self.canvas.create_text(doc_x + doc_w / 2, doc_y + doc_h / 2 - 10,
                                 text="Shared Document", font=("Segoe UI", 9), fill=theme.TEXT_MUTED)
        self.canvas.create_text(doc_x + doc_w / 2, doc_y + doc_h / 2 + 12,
                                 text=f"v{self.document_version}", font=("Segoe UI", 16, "bold"),
                                 fill=theme.TEXT_DARK)

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

                if event["type"] == "rw_event":
                    role = event["role"]
                    rid = event["id"]
                    action = event["action"]
                    violation = event.get("violation", False)
                    self.document_version = event["document"]

                    display_state = "violation" if violation else action
                    if role == "reader":
                        self.reader_states[rid] = display_state
                    else:
                        self.writer_states[rid] = display_state

                    self.draw_state()

                    if violation:
                        self.log(f"⚠ Overlap violation: {role.capitalize()} {rid} {action} "
                                  f"while another writer/reader was active!")

                elif event["type"] == "rw_finished":
                    role = event["role"]
                    rid = event["id"]
                    if role == "reader":
                        self.reader_states[rid] = "idle"
                    else:
                        self.writer_states[rid] = "idle"
                    self.draw_state()

                elif event["type"] == "rw_done":
                    violations = event["violation_count"]
                    duration = time.time() - self.start_time

                    log_run("readers_writers", self.current_mode, duration, violation_count=violations)

                    if violations == 0:
                        self.result_label.config(
                            text="✓ No overlapping access detected. Readers/writers stayed mutually exclusive.",
                            fg=theme.SUCCESS)
                        self.log(f"Result: no violations. Total time: {duration:.2f}s. Logged to database.")
                    else:
                        self.result_label.config(
                            text=f"✗ {violations} overlap violation(s) detected!",
                            fg=theme.DANGER)
                        self.log(f"Result: {violations} violations found. "
                                 f"Total time: {duration:.2f}s. Logged to database.")

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def run_safe_demo(self):
        self._run(safe_mode=True)

    def run_unsafe_demo(self):
        self._run(safe_mode=False)

    def _run(self, safe_mode):
        if self.running:
            return
        self.running = True
        self.current_mode = "safe" if safe_mode else "unsafe"
        self.start_time = time.time()
        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()
        self.reader_states = {i: "idle" for i in range(NUM_READERS)}
        self.writer_states = {i: "idle" for i in range(NUM_WRITERS)}
        self.document_version = 0
        self.draw_state()
        self.result_label.config(text="")
        mode_text = "SAFE (mutex + wrt semaphores)" if safe_mode else "UNSAFE (no locking)"
        self.log(f">>> Starting {mode_text} demo with {NUM_READERS} readers, {NUM_WRITERS} writers...")

        def worker():
            run_readers_writers(NUM_READERS, NUM_WRITERS, RW_ITERATIONS, safe_mode, self.event_queue)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()