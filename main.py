import multiprocessing
from logger import init_db
from gui import ConcurrencyLabApp
import tkinter as tk

if __name__ == "__main__":
    multiprocessing.freeze_support()
    init_db()
    root = tk.Tk()
    app = ConcurrencyLabApp(root)
    root.mainloop()