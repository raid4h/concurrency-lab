import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import math
import time

from philosophers import run_philosophers
from logger import log_run
import theme
from config import NUM_PHILOSOPHERS


class DiningPhilosophersTab(tk.Frame):
    STATE_COLORS = {
        "thinking": "#cbd5c1",
        "hungry": "#dda15e",
        "picked_first_fork": "#e08e45",
        "eating": "#6a994e",
        "done": "#a8c3a1",
        "stuck": "#bc4749",
    }

    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.start_time = None
        self.current_mode = None
        self.phil_states = {i: "thinking" for i in range(NUM_PHILOSOPHERS)}
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_card(self)

        tk.Label(card, text="Dining Philosophers Problem", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card, text="Five philosophers, five forks — demonstrates deadlock and how to avoid it.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)\
            .pack(anchor="w", padx=16, pady=(0, 10))

        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe Demo (No Deadlock)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe Demo (May Deadlock)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        self.status_label = tk.Label(card, text="Ready.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        self.canvas = tk.Canvas(card, width=380, height=380, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack(pady=6)

        legend = tk.Label(card,
                           text="Grey = thinking    Amber = hungry    Orange = has 1 fork    "
                                "Green = eating    Red = stuck (deadlocked)",
                           font=("Segoe UI", 8), bg=theme.CARD_BG, fg=theme.TEXT_MUTED)
        legend.pack(pady=(0, 6))

        self.log_area = scrolledtext.ScrolledText(card, width=70, height=7, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(6, 16), padx=16)

        self.draw_table()

    def log(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def draw_table(self):
        self.canvas.delete("all")
        cx, cy = 190, 190
        table_r = 65
        phil_r = 125
        node_r = 30

        self.canvas.create_oval(cx - table_r, cy - table_r, cx + table_r, cy + table_r,
                                 fill="#e0e8d9", outline=theme.BORDER, width=2)

        for i in range(NUM_PHILOSOPHERS):
            angle = math.radians(i * (360 / NUM_PHILOSOPHERS) - 90)
            x = cx + phil_r * math.cos(angle)
            y = cy + phil_r * math.sin(angle)

            state = self.phil_states.get(i, "thinking")
            color = self.STATE_COLORS.get(state, "#cbd5c1")

            self.canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                     fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text=f"P{i}", font=("Segoe UI", 11, "bold"), fill="white")
            self.canvas.create_text(x, y + node_r + 13, text=state, font=("Segoe UI", 8), fill=theme.TEXT_MUTED)

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

                if event["type"] == "philosopher":
                    self.phil_states[event["id"]] = event["state"]
                    self.draw_table()
                    self.status_label.config(text=f"{event['name']}: {event['state']}", fg=theme.TEXT_DARK)

                elif event["type"] == "philosopher_done":
                    stuck = event["stuck"]
                    duration = time.time() - self.start_time
                    deadlock_flag = 1 if stuck else 0

                    log_run("dining_philosophers", self.current_mode, duration,
                             deadlock_detected=deadlock_flag)

                    if stuck:
                        for name in stuck:
                            pid = int(name.split("-")[1])
                            self.phil_states[pid] = "stuck"
                        self.draw_table()
                        self.status_label.config(text="⚠ DEADLOCK DETECTED!", fg=theme.DANGER)
                        self.log(f"!! DEADLOCK: these philosophers never finished: {stuck}")
                        self.log(f">>> Run took {duration:.2f}s before timeout. Logged to database.")
                    else:
                        self.status_label.config(text="All philosophers finished eating.", fg=theme.SUCCESS)
                        self.log(f"All philosophers finished successfully in {duration:.2f}s, no deadlock.")
                        self.log(">>> Logged to database.")

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
        self.phil_states = {i: "thinking" for i in range(NUM_PHILOSOPHERS)}
        self.draw_table()
        mode_text = "SAFE (resource ordering fix)" if safe_mode else "UNSAFE (may deadlock)"
        self.log(f">>> Starting {mode_text} demo...")

        def worker():
            run_philosophers(event_queue=self.event_queue, safe_mode=safe_mode,
                              num_philosophers=NUM_PHILOSOPHERS)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()