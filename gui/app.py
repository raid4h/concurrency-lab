"""
The top-level application shell: creates the window, applies the theme,
and assembles every individual tab into one tabbed notebook.
"""

import tkinter as tk
from tkinter import ttk

import theme
from .producer_consumer_tab import ProducerConsumerTab
from .philosophers_tab import DiningPhilosophersTab
from .process_tab import ProcessTab
from .readers_writers_tab import ReadersWritersTab
from .deadlock_detector_tab import DeadlockDetectorTab  # NEW
from .stats_tab import StatsTab


class ConcurrencyLabApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ConcurrencyLab - OS Concurrency Demonstrator")
        self.root.geometry("680x820")   # initial window size (a bit wider, room for scrollbar)
        self.root.minsize(680, 600)     # can go shorter now - tabs scroll instead of clipping

        # Apply the forest color theme and build the dark header banner
        style = theme.apply_theme(root)
        theme.build_header(root, "Process & Thread Synchronization Demonstrator")

        # The notebook is the tabbed container every demo tab lives inside
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        # Create each tab (each one builds its own UI inside its own __init__)
        pc_tab = ProducerConsumerTab(notebook)
        phil_tab = DiningPhilosophersTab(notebook)
        proc_tab = ProcessTab(notebook)
        rw_tab = ReadersWritersTab(notebook)
        dd_tab = DeadlockDetectorTab(notebook)  # NEW
        stats_tab = StatsTab(notebook)

        # Register each tab with the notebook, in the order they should appear
        notebook.add(pc_tab, text="  Producer – Consumer  ")
        notebook.add(phil_tab, text="  Dining Philosophers  ")
        notebook.add(proc_tab, text="  Multi-Process Counter  ")
        notebook.add(rw_tab, text="  Readers – Writers  ")
        notebook.add(dd_tab, text="  Deadlock Detector  ")  # NEW
        notebook.add(stats_tab, text="  Performance Stats  ")