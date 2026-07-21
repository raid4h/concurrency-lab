import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time

from buffer import Buffer
from broken_buffer import BrokenBuffer
from producer import producer
from consumer import consumer
from logger import log_run
import theme
from config import NUM_ITEMS, CAPACITY


class ProducerConsumerTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.BG_LIGHT)
        self.event_queue = queue.Queue()
        self.running = False
        self.start_time = None
        self.violation_count = 0
        self.current_mode = None
        self._build_ui()
        self.poll_queue()

    def _build_ui(self):
        card = theme.build_scrollable_card(self)  # scrollable, so content can grow safely

        tk.Label(card, text="Producer–Consumer Problem", font=theme.FONT_HEADER,
                 bg=theme.CARD_BG, fg=theme.TEXT_DARK).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(card, text="A shared buffer with limited capacity, accessed by producer and consumer threads.",
                 font=theme.FONT_BODY, bg=theme.CARD_BG, fg=theme.TEXT_MUTED)\
            .pack(anchor="w", padx=16, pady=(0, 10))

        button_frame = tk.Frame(card, bg=theme.CARD_BG)
        button_frame.pack(pady=6)

        self.safe_btn = ttk.Button(button_frame, text="Run Safe Demo", style="Safe.TButton",
                                    command=self.run_safe_demo)
        self.safe_btn.grid(row=0, column=0, padx=6)

        self.unsafe_btn = ttk.Button(button_frame, text="Run Unsafe Demo (Race Condition)",
                                      style="Unsafe.TButton", command=self.run_unsafe_demo)
        self.unsafe_btn.grid(row=0, column=1, padx=6)

        self.status_label = tk.Label(card, text="Shelf: empty | Capacity: -", font=theme.FONT_BODY,
                                      bg=theme.CARD_BG, fg=theme.TEXT_DARK)
        self.status_label.pack(pady=8)

        self.canvas = tk.Canvas(card, width=560, height=100, bg="white",
                                 highlightbackground=theme.BORDER, highlightthickness=1)
        self.canvas.pack(pady=6, padx=16)

        self.log_area = scrolledtext.ScrolledText(card, width=70, height=13, state="disabled",
                                                    font=theme.FONT_MONO, bg="#1b2e1f", fg="#eef2e6",
                                                    insertbackground="white", relief="flat")
        self.log_area.pack(pady=(10, 16), padx=16)

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
            self.canvas.create_rectangle(x, 20, x + box_size, 20 + box_size,
                                          outline=theme.BORDER, width=2)

        fill_color = theme.DANGER if violation else theme.ACCENT
        for i, item in enumerate(shelf_items):
            x = start_x + i * (box_size + gap)
            self.canvas.create_rectangle(x, 20, x + box_size, 20 + box_size, fill=fill_color, outline="")
            label = item.replace("item-", "") if item else "?"
            self.canvas.create_text(x + box_size / 2, 20 + box_size / 2, text=label,
                                     fill="white", font=("Segoe UI", 10, "bold"))

    def poll_queue(self):
        try:
            while True:
                event = self.event_queue.get_nowait()

                if event == "DONE":
                    self.running = False
                    self.safe_btn.config(state="normal")
                    self.unsafe_btn.config(state="normal")

                    duration = time.time() - self.start_time
                    log_run("producer_consumer", self.current_mode, duration,
                             violation_count=self.violation_count)

                    self.log(f">>> Demo finished in {duration:.2f}s. "
                             f"Violations: {self.violation_count}. Logged to database.\n")
                    continue

                shelf = event["shelf"]
                capacity = event["capacity"]
                violation = event.get("violation", False)
                if violation:
                    self.violation_count += 1

                self.draw_shelf(shelf, capacity, violation)

                size_text = f"Shelf: {shelf}   |   Size: {len(shelf)}/{capacity}"
                if violation:
                    size_text += "   ⚠ CAPACITY VIOLATED"
                self.status_label.config(text=size_text, fg=theme.DANGER if violation else theme.TEXT_DARK)

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
        self.current_mode = "safe"
        self.violation_count = 0
        self.start_time = time.time()
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
        self.current_mode = "unsafe"
        self.violation_count = 0
        self.start_time = time.time()
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