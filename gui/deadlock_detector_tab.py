"""
GUI tab for the Deadlock DETECTION + RECOVERY demo. Draws the live
wait-for graph as nodes (philosophers) with arrows (who's waiting on
whom): red highlights a detected cycle, amber marks a philosopher that
recovery has forcibly terminated to break that cycle.

Layout: terminal docked on the LEFT (fixed width), graph diagram
centered in the remaining space, matching the Philosophers tab.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import math
import time

from deadlock_detector import run_detection_demo
from logger import log_run
import theme
from config import NUM_PHILOSOPHERS  # reuses the same count (5) as the other Philosophers tab

# Layout constants - kept at the top so they're easy to tweak later
CONTENT_ROW_HEIGHT = 460   # total height reserved for the terminal+diagram row
TERMINAL_WIDTH = 260         # fixed pixel width of the right-docked terminal
DIAGRAM_SIZE = 240             # width/height of the graph diagram canvas


class DeadlockDetectorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()  # events flow from background threads into this queue
        self.running = False
        self.start_time = None
        self.current_mode = None

        # graph[i] = which philosopher i is currently waiting on (or None if not waiting)
        self.graph = {i: None for i in range(NUM_PHILOSOPHERS)}
        self.cycle = None          # list of philosopher ids forming a detected cycle, if any
        self.aborted_ids = set()     # NEW: philosopher ids terminated by recovery this run

        self._build_ui()
        self.poll_queue()  # start the repeating "check for new events" loop

    def _build_ui(self):
        card = theme.build_scrollable_card(self)

        # --- Title and short explanation, full width ---
        tk.Label(card, text="Deadlock Detection \u0026 Recovery (Wait-For Graph)", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text="A background thread builds a live wait-for graph and searches it for "
                      "cycles via DFS. The moment a cycle is confirmed, RECOVERY triggers "
                      "automatically: a victim philosopher is terminated and its held fork is "
                      "forcibly released, breaking the deadlock so the rest can finish.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # --- Buttons, full width, centered ---
        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe (No Cycle Expected)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe (Detect + Recover)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        # --- Status line, full width, centered ---
        self.status_label = tk.Label(card, text="Ready.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        # --- Two-column row: TERMINAL docked left, GRAPH centered in the rest ---
        content_row = tk.Frame(card, bg=theme.CARD_BG, height=CONTENT_ROW_HEIGHT)
        content_row.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content_row.pack_propagate(False)  # keep a stable height for place() to center within

        # LEFT column: terminal, docked right... (kept consistent with the
        # Philosophers tab's proven pattern: width passed directly to
        # place(), NOT the Frame constructor, plus pack_propagate(False)
        # as a safety net, and no width= on the ScrolledText itself,
        # since Text/ScrolledText width is measured in CHARACTERS, not
        # pixels - passing width=1 there was the original "too-thin
        # terminal" bug from earlier in this project.)
        terminal_frame = tk.Frame(content_row, bg=theme.CARD_BG)
        terminal_frame.place(relx=1.0, rely=0.0, anchor="ne",
                              width=TERMINAL_WIDTH, relheight=1.0)
        terminal_frame.pack_propagate(False)

        self.log_area = scrolledtext.ScrolledText(terminal_frame, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(fill="both", expand=True)

        # RIGHT area: the wait-for graph, centered independently of the terminal
        graph_frame = tk.Frame(content_row, bg=theme.CARD_BG)
        graph_frame.place(relx=0.5, rely=0.0, anchor="n")

        self.canvas = tk.Canvas(graph_frame, width=DIAGRAM_SIZE, height=DIAGRAM_SIZE, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack()

        # Legend now has THREE entries (added "Aborted" for recovery
        # victims), using real colored swatches pulled directly from
        # the same colors used in draw_graph() below, so the legend
        # can never drift out of sync with what's actually drawn.
        legend_items = [
            (theme.BORDER, "Not waiting"),
            (theme.DANGER, "Part of a detected cycle"),
            (theme.WARNING, "Aborted (recovery victim)"),
        ]
        legend = theme.build_legend(graph_frame, legend_items, columns=3)
        legend.pack(pady=(8, 0))

        arrow_note = tk.Label(graph_frame, text="Arrow = 'is waiting for'",
                               font=("Segoe UI", 8), bg=theme.CARD_BG, fg=theme.TEXT_MUTED)
        arrow_note.pack(pady=(2, 0))

        self.draw_graph()  # draw the initial (empty) graph before anything runs

    def log(self, message):
        """Appends a line of text to the terminal box."""
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)  # auto-scroll to the newest line
        self.log_area.config(state="disabled")

    def _clear_log(self):
        """Wipes the terminal box before starting a fresh run."""
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def draw_graph(self):
        """
        Redraws the wait-for graph based on self.graph / self.cycle /
        self.aborted_ids. A node's color is decided with a priority
        order: aborted (amber) takes precedence over "in cycle" (red),
        since a terminated philosopher should visually read as
        "already dealt with" rather than "still deadlocked."
        """
        self.canvas.delete("all")

        cx, cy = 130, 130   # center point of the canvas
        radius = 88           # distance of each philosopher node from the center
        node_r = 20             # radius of each drawn node circle

        cycle_set = set(self.cycle) if self.cycle else set()

        # Compute where each philosopher node sits, evenly spaced around a circle
        positions = {}
        for i in range(NUM_PHILOSOPHERS):
            angle = math.radians(i * (360 / NUM_PHILOSOPHERS) - 90)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            positions[i] = (x, y)

        # Draw the "waiting for" arrows FIRST, so node circles render on top
        for phil_id, waiting_on in self.graph.items():
            if waiting_on is None:
                continue  # this philosopher isn't currently blocked on anyone

            x1, y1 = positions[phil_id]
            x2, y2 = positions[waiting_on]

            is_cycle_edge = phil_id in cycle_set and waiting_on in cycle_set
            edge_color = theme.DANGER if is_cycle_edge else theme.TEXT_MUTED

            self.canvas.create_line(x1, y1, x2, y2, fill=edge_color, width=2,
                                     arrow=tk.LAST, arrowshape=(10, 12, 4))

        # Draw the philosopher nodes on top of the arrows
        for i in range(NUM_PHILOSOPHERS):
            x, y = positions[i]

            # PRIORITY: aborted > in-cycle > idle. Once terminated, a
            # philosopher stays amber even if it was previously drawn
            # red as part of the cycle that led to its termination.
            if i in self.aborted_ids:
                color = theme.WARNING
            elif i in cycle_set:
                color = theme.DANGER
            else:
                color = theme.BORDER

            self.canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                     fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text=f"P{i}", font=("Segoe UI", 10, "bold"), fill="white")

    def poll_queue(self):
        """Runs every 50ms: checks for new events from background threads."""
        try:
            while True:
                event = self.event_queue.get_nowait()

                if event == "DONE":
                    self.running = False
                    self.safe_btn.config(state="normal")
                    self.unsafe_btn.config(state="normal")
                    self.log(">>> Demo finished.\n")
                    continue

                if event["type"] == "graph_snapshot":
                    # A fresh snapshot of who's waiting on whom - redraw
                    self.graph = event["graph"]
                    self.draw_graph()

                elif event["type"] == "cycle_detected":
                    # The detector algorithm found a genuine cycle - highlight it
                    self.cycle = event["cycle"]
                    self.draw_graph()
                    cycle_text = " → ".join(f"P{p}" for p in self.cycle) + f" → P{self.cycle[0]}"
                    self.status_label.config(text="⚠ DEADLOCK DETECTED (cycle found)", fg=theme.DANGER)
                    self.log(f"!! Detector found a cycle in the wait-for graph: {cycle_text}")

                elif event["type"] == "recovery_action":
                    # NEW: recovery just terminated one philosopher to
                    # break the cycle - update the diagram and log it.
                    victim = event["victim"]
                    freed_fork = event["freed_fork"]
                    self.aborted_ids.add(victim)
                    self.draw_graph()
                    self.status_label.config(
                        text=f"Recovery: terminated Philosopher {victim} to break the cycle",
                        fg=theme.WARNING
                    )
                    self.log(f">>> RECOVERY: Philosopher {victim} forcibly terminated. "
                             f"Fork {freed_fork} preempted and released to the remaining philosophers.")

                elif event["type"] == "detection_done":
                    duration = time.time() - self.start_time
                    cycle = event["cycle"]
                    stuck = event["stuck"]
                    victims = event["victims"]

                    # Log this run's result to the same shared database as every other tab.
                    # A cycle being FOUND is still logged as 1, even though it was recovered -
                    # detection is what the stats chart is measuring, and detection did occur.
                    log_run("deadlock_detection", self.current_mode, duration,
                            deadlock_detected=1 if cycle else 0)

                    if cycle and victims:
                        # The expected, successful path: a cycle formed, recovery
                        # terminated some victim(s), and everyone else should have
                        # finished normally as a result.
                        unexpected_stuck = [p for p in stuck if p not in victims]
                        self.status_label.config(text="✓ Deadlock detected and recovered.",
                                                  fg=theme.SUCCESS)
                        self.log(f">>> Deadlock recovered: {victims} terminated to break the cycle.")
                        if unexpected_stuck:
                            self.log(f"!! Note: {unexpected_stuck} did not finish either - "
                                     f"may need a longer timeout for this many philosophers.")
                        else:
                            self.log(f">>> All remaining philosophers finished normally after recovery.")
                        self.log(f">>> Total time: {duration:.2f}s. Logged to database.")
                    elif cycle:
                        # A cycle was found but recovery never got a chance to act on it
                        # (e.g. timing edge case) - fall back to the old-style report.
                        self.log(f">>> Confirmed deadlock among: {stuck}. "
                                 f"Total time: {duration:.2f}s. Logged to database.")
                    else:
                        self.status_label.config(text="✓ No cycle found. All philosophers finished.",
                                                  fg=theme.SUCCESS)
                        self.log(f"No deadlock: all philosophers finished in {duration:.2f}s. "
                                 f"Logged to database.")

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def run_safe_demo(self):
        self._run(safe_mode=True)

    def run_unsafe_demo(self):
        self._run(safe_mode=False)

    def _run(self, safe_mode):
        if self.running:
            return  # ignore clicks while a demo is already in progress

        self.running = True
        self.current_mode = "safe" if safe_mode else "unsafe"
        self.start_time = time.time()

        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()

        # Reset the graph/cycle/aborted display for a clean new run
        self.graph = {i: None for i in range(NUM_PHILOSOPHERS)}
        self.cycle = None
        self.aborted_ids = set()
        self.draw_graph()
        self.status_label.config(text="Detector running...", fg=theme.TEXT_DARK)

        mode_text = "SAFE (resource ordering)" if safe_mode else "UNSAFE (detect + recover)"
        self.log(f">>> Starting {mode_text} demo. Detector is watching for cycles...")

        # Run the actual simulation on a background thread so the GUI never freezes
        def worker():
            run_detection_demo(NUM_PHILOSOPHERS, safe_mode, self.event_queue)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()