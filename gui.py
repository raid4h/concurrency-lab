import tkinter as tk
from tkinter import scrolledtext
import threading
import queue

from buffer import Buffer
from broken_buffer import BrokenBuffer
from producer import producer
from consumer import consumer

NUM_ITEMS = 8
CAPACITY = 3


class ConcurrencyLabApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ConcurrencyLab - Producer/Consumer Visualizer")
        self.root.geometry("620x520")

        self.event_queue = queue.Queue()
        self.running = False

        # --- Buttons ---
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)

        self.safe_btn = tk.Button(button_frame, text="Run Safe Demo", width=20,
                                   command=self.run_safe_demo, bg="#c8e6c9")
        self.safe_btn.grid(row=0, column=0, padx=5)

        self.unsafe_btn = tk.Button(button_frame, text="Run Unsafe Demo (Race Condition)", width=30,
                                     command=self.run_unsafe_demo, bg="#ffcdd2")
        self.unsafe_btn.grid(row=0, column=1, padx=5)

        # --- Status label ---
        self.status_label = tk.Label(root, text="Shelf: empty | Capacity: -", font=("Arial", 12))
        self.status_label.pack(pady=5)

        # --- Canvas for shelf visualization ---
        self.canvas = tk.Canvas(root, width=580, height=100, bg="white")
        self.canvas.pack(pady=10)

        # --- Log area ---
        self.log_area = scrolledtext.ScrolledText(root, width=72, height=16, state="disabled")
        self.log_area.pack(pady=10)

        self.poll_queue()

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

        self.root.after(50, self.poll_queue)

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


if __name__ == "__main__":
    root = tk.Tk()
    app = ConcurrencyLabApp(root)
    root.mainloop()