"""
GUI tab for the Dining Philosophers deadlock/prevention demo.
Layout: a tall log/terminal box docked on the LEFT (fixed width), and
the circular diagram + its legend TRULY CENTERED in the remaining space
to the right, using place() for guaranteed centering (more reliable
than pack()'s default centering, which depends on exact frame sizing).
"""

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
    # Maps each philosopher state to the color drawn on the diagram
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
        self.event_queue = queue.Queue()          # events from the background thread arrive here
        self.running = False                        # True while a demo is actively running
        self.start_time = None                        # used to measure how long each run takes
        self.current_mode = None                        # "safe" or "unsafe", set when a run starts
        self.phil_states = {i: "thinking" for i in range(NUM_PHILOSOPHERS)}  # current state per philosopher
        self._build_ui()
        self.poll_queue()  # kick off the repeating "check for new events" loop

    def _build_ui(self):
        # Wraps everything in a scrollable card (safety net if content
        # ever grows taller than the visible window).
        card = theme.build_scrollable_card(self)

        # --- Title + short description, full width at the top ---
        tk.Label(card, text="Dining Philosophers Problem", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card, text="Five philosophers, five forks — demonstrates deadlock and how to avoid it.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)\
            .pack(anchor="w", padx=16, pady=(0, 10))

        # --- Buttons, full width, centered ---
        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe Demo (No Deadlock)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe Demo (May Deadlock)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        # --- Status line, full width, centered ---
        self.status_label = tk.Label(card, text="Ready.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        # --- Two-column row: TERMINAL docked left, DIAGRAM centered in the rest ---
        # This row holds both columns side by side. We give it a fixed,
        # generous height so place()'s percentage-based centering below
        # has a stable area to center within.
        content_row = tk.Frame(card, bg=theme.CARD_BG, height=420)
        content_row.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content_row.pack_propagate(False)  # keep the 420px height even though children are smaller

        # LEFT column: the terminal/log box, docked to the left edge with
        # a fixed pixel width (so it doesn't resize when the window does).
        left_col = tk.Frame(content_row, bg=theme.CARD_BG, width=230)
        left_col.pack(side="left", fill="y", padx=(0, 14))
        left_col.pack_propagate(False)  # keep the 230px width regardless of the log box's own sizing

        self.log_area = scrolledtext.ScrolledText(left_col, width=28, height=20, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        # fill="both", expand=True makes the log box stretch to fill the
        # entire fixed-width left_col frame, however wide/tall that ends up.
        self.log_area.pack(fill="both", expand=True)

        # RIGHT area: takes up all remaining horizontal space next to the terminal.
        right_col = tk.Frame(content_row, bg=theme.CARD_BG)
        right_col.pack(side="left", fill="both", expand=True)

        # diagram_frame holds the canvas + legend together as a single unit,
        # so they move/center as one block.
        diagram_frame = tk.Frame(right_col, bg=theme.CARD_BG)

        # place(relx=0.5, rely=0.0, anchor="n") is the key centering trick:
        # relx=0.5 means "50% across right_col's width" (i.e. dead center),
        # anchor="n" means diagram_frame's TOP-CENTER point sits at that
        # spot. This stays perfectly centered even if right_col's width
        # changes (e.g. window resize), unlike pack()'s centering, which
        # can behave inconsistently depending on sibling widget sizing.
        diagram_frame.place(relx=0.5, rely=0.0, anchor="n")

        # Smaller diagram (260x260) so it comfortably fits beside the terminal.
        self.canvas = tk.Canvas(diagram_frame, width=260, height=260, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack()  # centered within diagram_frame automatically, since it's the only child

        legend = tk.Label(diagram_frame,
                           text="Grey = thinking    Amber = hungry    Orange = has 1 fork\n"
                                "Green = eating    Red = stuck (deadlocked)",
                           font=("Segoe UI", 8), bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                           justify="center")
        legend.pack(pady=(8, 0))  # sits directly under the diagram, as requested

        self.draw_table()  # draw the initial (all "thinking") state

    def log(self, message):
        """Appends one line of text to the terminal box and scrolls to it."""
        self.log_area.config(state="normal")   # must be "normal" to allow editing
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)               # auto-scroll so the newest line is visible
        self.log_area.config(state="disabled")  # lock it again so the user can't type in it

    def _clear_log(self):
        """Wipes the terminal box before starting a fresh run."""
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def draw_table(self):
        """
        Redraws the round table and all 5 philosopher nodes, positioned
        in a circle and color-coded by their current state. Coordinates
        are scaled to fit the smaller 260x260 canvas.
        """
        self.canvas.delete("all")  # wipe the canvas before redrawing everything

        cx, cy = 130, 130   # center point of the (smaller) canvas
        table_r = 45          # radius of the round table graphic
        phil_r = 90             # distance of each philosopher node from the center
        node_r = 22              # radius of each philosopher's own circle

        # Draw the round table first, so philosopher nodes render on top of it
        self.canvas.create_oval(cx - table_r, cy - table_r, cx + table_r, cy + table_r,
                                 fill="#e0e8d9", outline=theme.BORDER, width=2)

        # Place each philosopher evenly spaced around the table (360/5 = 72° apart)
        for i in range(NUM_PHILOSOPHERS):
            angle = math.radians(i * (360 / NUM_PHILOSOPHERS) - 90)  # -90 so P0 starts at the top
            x = cx + phil_r * math.cos(angle)
            y = cy + phil_r * math.sin(angle)

            state = self.phil_states.get(i, "thinking")
            color = self.STATE_COLORS.get(state, "#cbd5c1")

            self.canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                     fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text=f"P{i}", font=("Segoe UI", 10, "bold"), fill="white")
            self.canvas.create_text(x, y + node_r + 11, text=state, font=("Segoe UI", 7), fill=theme.TEXT_MUTED)

    def poll_queue(self):
        """Runs every 50ms: checks for new events from the background thread."""
        try:
            while True:
                event = self.event_queue.get_nowait()  # grab the next event without blocking

                if event == "DONE":
                    # The whole demo run has finished (all threads joined)
                    self.running = False
                    self.safe_btn.config(state="normal")
                    self.unsafe_btn.config(state="normal")
                    self.log(">>> Demo finished.\n")
                    continue

                if event["type"] == "philosopher":
                    # One philosopher changed state - update and redraw
                    self.phil_states[event["id"]] = event["state"]
                    self.draw_table()
                    self.status_label.config(text=f"{event['name']}: {event['state']}", fg=theme.TEXT_DARK)

                elif event["type"] == "philosopher_done":
                    # The simulation reported its final outcome
                    stuck = event["stuck"]
                    duration = time.time() - self.start_time
                    deadlock_flag = 1 if stuck else 0

                    # Save this run's result to the shared SQLite database
                    log_run("dining_philosophers", self.current_mode, duration,
                            deadlock_detected=deadlock_flag)

                    if stuck:
                        # Color every permanently-stuck philosopher red on the diagram
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
            pass  # no new events right now - that's fine, just check again shortly

        self.after(50, self.poll_queue)  # reschedule this same check in 50ms

    def run_safe_demo(self):
        self._run(safe_mode=True)

    def run_unsafe_demo(self):
        self._run(safe_mode=False)

    def _run(self, safe_mode):
        if self.running:
            return  # ignore extra clicks while a demo is already in progress

        self.running = True
        self.current_mode = "safe" if safe_mode else "unsafe"
        self.start_time = time.time()

        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()

        # Reset every philosopher back to "thinking" for a clean new run
        self.phil_states = {i: "thinking" for i in range(NUM_PHILOSOPHERS)}
        self.draw_table()

        mode_text = "SAFE (resource ordering fix)" if safe_mode else "UNSAFE (may deadlock)"
        self.log(f">>> Starting {mode_text} demo...")

        # The actual simulation runs on a background thread, so the GUI
        # (and its 50ms poll_queue loop) never freezes while it's running.
        def worker():
            run_philosophers(event_queue=self.event_queue, safe_mode=safe_mode,
                              num_philosophers=NUM_PHILOSOPHERS)
            self.event_queue.put("DONE")  # signal completion back to the GUI thread

        threading.Thread(target=worker, daemon=True).start()