import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import math

from buffer import Buffer
from broken_buffer import BrokenBuffer
from producer import producer
from consumer import consumer
from philosophers import run_philosophers

NUM_ITEMS = 8
CAPACITY = 3
NUM_PHILOSOPHERS = 5


class ProducerConsumerTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.event_queue = queue.Queue()
        self.running = False
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        self.safe_btn = tk.Button(button_frame, text="Run Safe Demo", width=20,
                                   command=self.run_safe_demo, bg="#c8e6c9")
        self.safe_btn.grid(row=0, column=0, padx=5)

        self.unsafe_btn = tk.Button(button_frame, text="Run Unsafe Demo (Race Condition)", width=30,
                                     command=self.run_unsafe_demo, bg="#ffcdd2")
        self.unsafe_btn.grid(row=0, column=1, padx=5)

        self.status_label = tk.Label(self, text="Shelf: empty | Capacity: -", font=("Arial", 12))
        self.status_label.pack(pady=5)

        self.canvas = tk.Canvas(self, width=580, height=100, bg="white")
        self.canvas.pack(pady=10)

        self.log_area = scrolledtext.ScrolledText(self, width=72, height=14, state="disabled")
        self.log_area.pack(pady=10)

    def log(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def draw_shelf(self, shelf_items, capacity, violation=False):
        self.canvas.delete("all")
        box_size = 60
        gap = 10
        start_x = 10

        for i in range(capacity):
            x = start_x + i * (box_size + gap)
            self.canvas.create_rectangle(x, 20, x + box_size, 20 + box_size, outline="black", width=2)

        fill_color = "red" if violation else "#64b5f6"
        for i, item in enumerate(shelf_items):
            x = start_x + i * (box_size + gap)
            self.canvas.create_rectangle(x, 20, x + box_size, 20 + box_size, fill=fill_color)
            label = item.replace("item-", "") if item else "?"
            self.canvas.create_text(x + box_size / 2, 20 + box_size / 2, text=label,
                                     fill="white", font=("Arial", 10, "bold"))

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

                shelf = event["shelf"]
                capacity = event["capacity"]
                violation = event.get("violation", False)

                self.draw_shelf(shelf, capacity, violation)

                size_text = f"Shelf: {shelf} | Size: {len(shelf)}/{capacity}"
                if violation:
                    size_text += "   !! CAPACITY VIOLATED !!"
                self.status_label.config(text=size_text, fg="red" if violation else "black")

                if event["action"] == "produced":
                    self.log(f"Produced: {event['item']}")
                elif event["action"] == "consumed":
                    self.log(f"Consumed: {event['item']}")
                elif event["action"] == "waiting_full":
                    self.log("Producer waiting (shelf full)...")
                elif event["action"] == "waiting_empty":
                    self.log("Consumer waiting (shelf empty)...")

        except queue.Empty:
            pass

        self.after(50, self.poll_queue)

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")

    def run_safe_demo(self):
        if self.running:
            return
        self.running = True
        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()
        self.log(">>> Starting SAFE demo (with locks)...")

        shelf = Buffer(CAPACITY, event_queue=self.event_queue)
        self._start_threads(shelf, multiple=False)

    def run_unsafe_demo(self):
        if self.running:
            return
        self.running = True
        self.safe_btn.config(state="disabled")
        self.unsafe_btn.config(state="disabled")
        self._clear_log()
        self.log(">>> Starting UNSAFE demo (no locks — race condition likely)...")

        shelf = BrokenBuffer(CAPACITY, event_queue=self.event_queue)
        self._start_threads(shelf, multiple=True)

    def _start_threads(self, shelf, multiple):
        def worker():
            threads = []
            if multiple:
                for _ in range(3):
                    threads.append(threading.Thread(target=producer, args=(shelf, NUM_ITEMS)))
                for _ in range(3):
                    threads.append(threading.Thread(target=consumer, args=(shelf, NUM_ITEMS)))
            else:
                threads.append(threading.Thread(target=producer, args=(shelf, NUM_ITEMS)))
                threads.append(threading.Thread(target=consumer, args=(shelf, NUM_ITEMS)))

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.event_queue.put("DONE")

        threading.Thread(target=worker, daemon=True).start()


class DiningPhilosophersTab(tk.Frame):
    STATE_COLORS = {
        "thinking": "#e0e0e0",
        "hungry": "#ffd54f",
        "picked_first_fork": "#ffb74d",
        "eating": "#81c784",
        "done": "#90a4ae",
        "stuck": "#e53935",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.event_queue = queue.Queue()
        self.running = False
        self.phil_states = {i: "thinking" for i in range(NUM_PHILOSOPHERS)}
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        self.safe_btn = tk.Button(button_frame, text="Run Safe Demo (No Deadlock)", width=25,
                                   command=self.run_safe_demo, bg="#c8e6c9")
        self.safe_btn.grid(row=0, column=0, padx=5)

        self.unsafe_btn = tk.Button(button_frame, text="Run Unsafe Demo (May Deadlock)", width=28,
                                     command=self.run_unsafe_demo, bg="#ffcdd2")
        self.unsafe_btn.grid(row=0, column=1, padx=5)

        self.status_label = tk.Label(self, text="Ready.", font=("Arial", 12))
        self.status_label.pack(pady=5)

        self.canvas = tk.Canvas(self, width=400, height=400, bg="white")
        self.canvas.pack(pady=10)

        legend = tk.Label(self, text="Grey = thinking   Yellow = hungry   Orange = has 1 fork   "
                                      "Green = eating   Red = stuck (deadlocked)",
                           font=("Arial", 9))
        legend.pack()

        self.log_area = scrolledtext.ScrolledText(self, width=72, height=8, state="disabled")
        self.log_area.pack(pady=10)

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
        cx, cy = 200, 200
        table_r = 70
        phil_r = 130
        node_r = 30

        self.canvas.create_oval(cx - table_r, cy - table_r, cx + table_r, cy + table_r,
                                 fill="#d7ccc8", outline="black")

        for i in range(NUM_PHILOSOPHERS):
            angle = math.radians(i * (360 / NUM_PHILOSOPHERS) - 90)
            x = cx + phil_r * math.cos(angle)
            y = cy + phil_r * math.sin(angle)

            state = self.phil_states.get(i, "thinking")
            color = self.STATE_COLORS.get(state, "#e0e0e0")

            self.canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                     fill=color, outline="black", width=2)
            self.canvas.create_text(x, y, text=f"P{i}", font=("Arial", 11, "bold"))
            self.canvas.create_text(x, y + node_r + 12, text=state, font=("Arial", 8))

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
                    self.status_label.config(text=f"{event['name']}: {event['state']}", fg="black")

                elif event["type"] == "philosopher_done":
                    stuck = event["stuck"]
                    if stuck:
                        for name in stuck:
                            pid = int(name.split("-")[1])
                            self.phil_states[pid] = "stuck"
                        self.draw_table()
                        self.status_label.config(text="DEADLOCK DETECTED!", fg="red")
                        self.log(f"!! DEADLOCK: these philosophers never finished: {stuck}")
                    else:
                        self.status_label.config(text="All philosophers finished eating.", fg="green")
                        self.log("All philosophers finished successfully, no deadlock.")

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


class ConcurrencyLabApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ConcurrencyLab - OS Concurrency Demonstrator")
        self.root.geometry("650x680")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        pc_tab = ProducerConsumerTab(notebook)
        phil_tab = DiningPhilosophersTab(notebook)

        notebook.add(pc_tab, text="Producer-Consumer")
        notebook.add(phil_tab, text="Dining Philosophers")


if __name__ == "__main__":
    root = tk.Tk()
    app = ConcurrencyLabApp(root)
    root.mainloop()