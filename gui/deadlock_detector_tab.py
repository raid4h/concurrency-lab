"""
GUI tab for the Deadlock DETECTION demo. Draws the live wait-for graph
as a set of nodes (philosophers) with arrows (who's waiting on whom),
highlighting in red whichever nodes/edges form a detected cycle.

Layout: terminal docked on the LEFT (fixed width), graph diagram + legend
TRULY CENTERED in the remaining space via place(), same technique as
the Dining Philosophers tab.
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


class DeadlockDetectorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()  # events flow from background threads into this queue
        self.running = False
        self.start_time = None
        self.current_mode = None

        # graph[i] = which philosopher i is currently waiting on (or None if not waiting)
        self.graph = {i: None for i in range(NUM_PHILOSOPHERS)}
        self.cycle = None  # list of philosopher ids forming a detected cycle, if any

        self._build_ui()
        self.poll_queue()  # start the repeating "check for new events" loop

    def _build_ui(self):
        card = theme.build_scrollable_card(self)

        # --- Title and short explanation, full width ---
        tk.Label(card, text="Deadlock Detection (Wait-For Graph)", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card,
                 text="A background thread builds a live wait-for graph and searches it for "
                      "cycles via DFS - the same algorithm taught for single-instance resource "
                      "deadlock detection. A cycle means a mathematically confirmed deadlock.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                 wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # --- Buttons, full width, centered ---
        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe (No Cycle Expected)",
                                    style="Safe.TButton", command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe (Cycle Likely)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        # --- Status line, full width, centered ---
        self.status_label = tk.Label(card, text="Ready.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        # --- Two-column row: TERMINAL docked left, GRAPH centered in the rest ---
        content_row = tk.Frame(card, bg=theme.CARD_BG, height=420)
        content_row.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content_row.pack_propagate(False)  # keep a stable 420px height for place() to center within

        # LEFT column: the terminal/log box, docked left with a fixed pixel width
        left_col = tk.Frame(content_row, bg=theme.CARD_BG, width=230)
        left_col.pack(side="left", fill="y", padx=(0, 14))
        left_col.pack_propagate(False)  # keep the 230px width regardless of the log box's own sizing

        self.log_area = scrolledtext.ScrolledText(left_col, width=28, height=20, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(fill="both", expand=True)  # stretch to fill the fixed-width left_col

        # RIGHT area: everything to the right of the terminal
        right_col = tk.Frame(content_row, bg=theme.CARD_BG)
        right_col.pack(side="left", fill="both", expand=True)

        # graph_frame holds the canvas + legend as one block, centered as a unit
        graph_frame = tk.Frame(right_col, bg=theme.CARD_BG)

        # Same centering trick as the Philosophers tab: relx=0.5 pins the
        # horizontal midpoint of graph_frame to the exact center of
        # right_col, and stays correct even if the window is resized.
        graph_frame.place(relx=0.5, rely=0.0, anchor="n")

        # Smaller diagram (260x260) so it comfortably fits beside the terminal.
        self.canvas = tk.Canvas(graph_frame, width=260, height=260, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack()

        legend = tk.Label(graph_frame,
                           text="Grey = not waiting    Arrow = 'is waiting for'\n"
                                "Red = part of a detected deadlock cycle",
                           font=("Segoe UI", 8), bg=theme.CARD_BG, fg=theme.TEXT_MUTED,
                           justify="center")
        legend.pack(pady=(8, 0))

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
        Redraws the wait-for graph based on self.graph / self.cycle.
        Coordinates are scaled to fit the smaller 260x260 canvas.
        """
        self.canvas.delete("all")

        cx, cy = 130, 130   # center point of the (smaller) canvas
        radius = 88           # distance of each philosopher node from the center
        node_r = 20             # radius of each drawn node circle

        cycle_set = set(self.cycle) if self.cycle else set()  # for quick "is this in the cycle?" checks

        # Compute where each philosopher node sits, evenly spaced around a circle
        positions = {}
        for i in range(NUM_PHILOSOPHERS):
            angle = math.radians(i * (360 / NUM_PHILOSOPHERS) - 90)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            positions[i] = (x, y)

        # Draw the "waiting for" arrows FIRST, so node circles render on top of them
        for phil_id, waiting_on in self.graph.items():
            if waiting_on is None:
                continue  # this philosopher isn't currently blocked on anyone

            x1, y1 = positions[phil_id]
            x2, y2 = positions[waiting_on]

            # Color this edge red only if BOTH ends are part of the detected cycle
            is_cycle_edge = phil_id in cycle_set and waiting_on in cycle_set
            edge_color = theme.DANGER if is_cycle_edge else theme.TEXT_MUTED

            self.canvas.create_line(x1, y1, x2, y2, fill=edge_color, width=2,
                                     arrow=tk.LAST, arrowshape=(10, 12, 4))

        # Draw the philosopher nodes on top of the arrows
        for i in range(NUM_PHILOSOPHERS):
            x, y = positions[i]
            color = theme.DANGER if i in cycle_set else theme.BORDER
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

                elif event["type"] == "detection_done":
                    duration = time.time() - self.start_time
                    cycle = event["cycle"]
                    stuck = event["stuck"]

                    # Log this run's result to the same shared database as every other tab
                    log_run("deadlock_detection", self.current_mode, duration,
                            deadlock_detected=1 if cycle else 0)

                    if cycle:
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

        # Reset the graph/cycle display for a clean new run
        self.graph = {i: None for i in range(NUM_PHILOSOPHERS)}
        self.cycle = None
        self.draw_graph()
        self.status_label.config(text="Detector running...", fg=theme.TEXT_DARK)

        mode_text = "SAFE (resource ordering)" if safe_mode else "UNSAFE (may deadlock)"
        self.log(f">>> Starting {mode_text} demo. Detector is watching for cycles...")

        # Run the actual simulation on a background thread so the GUI never freezes
        def worker():
            run_detection_demo(NUM_PHILOSOPHERS, safe_mode, self.event_queue)
            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()