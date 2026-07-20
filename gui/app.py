import tkinter as tk
from tkinter import ttk

import theme
from .producer_consumer_tab import ProducerConsumerTab
from .philosophers_tab import DiningPhilosophersTab
from .process_tab import ProcessTab
from .readers_writers_tab import ReadersWritersTab
from .stats_tab import StatsTab


class ConcurrencyLabApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ConcurrencyLab - OS Concurrency Demonstrator")
        self.root.geometry("650x850")
        self.root.minsize(650, 760)

        style = theme.apply_theme(root)
        theme.build_header(root, "Process & Thread Synchronization Demonstrator")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        pc_tab = ProducerConsumerTab(notebook)
        phil_tab = DiningPhilosophersTab(notebook)
        proc_tab = ProcessTab(notebook)
        rw_tab = ReadersWritersTab(notebook)
        stats_tab = StatsTab(notebook)

        notebook.add(pc_tab, text="  Producer – Consumer  ")
        notebook.add(phil_tab, text="  Dining Philosophers  ")
        notebook.add(proc_tab, text="  Multi-Process Counter  ")
        notebook.add(rw_tab, text="  Readers – Writers  ")
        notebook.add(stats_tab, text="  Performance Stats  ")