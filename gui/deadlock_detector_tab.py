"""
GUI tab for the Deadlock DETECTION demo. Draws the live wait-for graph
as a set of nodes (philosophers) with arrows (who's waiting on whom),
highlighting in red whichever nodes/edges form a detected cycle.

Same layout technique as the Philosophers tab: terminal docked to the
RIGHT edge and stretched to fill the full height (more vertical room),
graph diagram centered at the true horizontal midpoint of the row
(independent of the terminal's width), matching "Ready" above it.
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

        # --- Status line, full width, centered - this is what we're matching below ---
        self.status_label = tk.Label(card, text="Ready.", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        # --- content_row: one fixed-size container holding BOTH the
        # terminal and the diagram, positioned independently with place(). ---
        content_row = tk.Frame(card, bg=theme.CARD_BG, height=CONTENT_ROW_HEIGHT)
        content_row.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content_row.pack_propagate(False)  # lock the height so place()'s percentages stay stable

        # --- TERMINAL: docked to the right edge, stretched to fill the
        # entire height of content_row for maximum vertical space. ---
        terminal_frame = tk.Frame(content_row, bg=theme.CARD_BG)
        # FIX: pass width=TERMINAL_WIDTH directly to place() itself (not
        # just the Frame constructor), forcing an exact pixel width that
        # can't be overridden by the ScrolledText child's own size request.
        terminal_frame.place(relx=1.0, rely=0.0, anchor="ne",
                              width=TERMINAL_WIDTH, relheight=1.0)
        # Extra safety net: disable child-based auto-resizing entirely.
        terminal_frame.pack_propagate(False)

        # Dropped the old 'width=1' (character-based, not pixels - the
        # actual cause of the too-thin terminal). fill="both" below makes
        # the real pixel size follow terminal_frame's actual size instead.
        self.log_area = scrolledtext.ScrolledText(terminal_frame, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(fill="both", expand=True)  # stretch to fill terminal_frame's actual size

        # --- GRAPH DIAGRAM: centered at the true horizontal midpoint of
        # content_row's full width, independent of the terminal's size. ---
        graph_frame = tk.Frame(content_row, bg=theme.CARD_BG)
        graph_frame.place(relx=0.5, rely=0.0, anchor="n")

        self.canvas = tk.Canvas(graph_frame, width=DIAGRAM_SIZE, height=DIAGRAM_SIZE, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack()

        # Only the two NODE colors get swatches here - "arrow" isn't a
        # fill color, it's a line/shape, so it gets a plain text note
        # underneath instead of a (misleading) colored square.
        legend_items = [
            (theme.BORDER, "Not waiting"),
            (theme.DANGER, "Part of a detected cycle"),
        ]
        legend = theme.build_legend(graph_frame, legend_items, columns=2)
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
        Redraws the wait-for graph based on self.graph / self.cycle.
        Coordinates are scaled to fit the DIAGRAM_SIZE x DIAGRAM_SIZE canvas.
        """
        self.canvas.delete("all")

        cx, cy = DIAGRAM_SIZE / 2, DIAGRAM_SIZE / 2   # center point of the canvas
        radius = 82           # distance of each philosopher node from the center
        node_r = 18             # radius of each drawn node circle

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
                                     arrow=tk.LAST, arrowshape=(9, 11, 4))

        # Draw the philosopher nodes on top of the arrows
        for i in range(NUM_PHILOSOPHERS):
            x, y = positions[i]
            color = theme.DANGER if i in cycle_set else theme.BORDER
            self.canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                     fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text=f"P{i}", font=("Segoe UI", 9, "bold"), fill="white")

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