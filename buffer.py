import threading

class Buffer:
    def __init__(self, capacity, event_queue=None):
        self.capacity = capacity
        self.items = []
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.event_queue = event_queue  # optional: lets the GUI watch what's happening

    def _report(self, action, item):
        if self.event_queue:
            self.event_queue.put({
                "action": action,
                "item": item,
                "shelf": list(self.items),
                "capacity": self.capacity
            })

    def put(self, item):
        with self.not_full:
            while len(self.items) >= self.capacity:
                self._report("waiting_full", item)
                self.not_full.wait()

            self.items.append(item)
            print(f"Produced: {item}  | Shelf now: {self.items}")
            self._report("produced", item)

            self.not_empty.notify()

    def get(self):
        with self.not_empty:
            while len(self.items) == 0:
                self._report("waiting_empty", None)
                self.not_empty.wait()

            item = self.items.pop(0)
            print(f"Consumed: {item}  | Shelf now: {self.items}")
            self._report("consumed", item)

            self.not_full.notify()
            return item