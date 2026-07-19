import time
import random

class BrokenBuffer:
    """Same idea as Buffer, but WITHOUT any locks — used to prove why synchronization matters."""
    def __init__(self, capacity, event_queue=None):
        self.capacity = capacity
        self.items = []
        self.event_queue = event_queue

    def _report(self, action, item):
        if self.event_queue:
            violation = len(self.items) > self.capacity
            self.event_queue.put({
                "action": action,
                "item": item,
                "shelf": list(self.items),
                "capacity": self.capacity,
                "violation": violation
            })

    def put(self, item):
        while len(self.items) >= self.capacity:
            time.sleep(0.01)
        time.sleep(random.uniform(0, 0.05))
        self.items.append(item)
        print(f"[UNSAFE] Produced: {item} | Shelf: {self.items} | Size: {len(self.items)}")
        self._report("produced", item)

    def get(self):
        while len(self.items) == 0:
            time.sleep(0.01)
        time.sleep(random.uniform(0, 0.05))
        item = self.items.pop(0)
        print(f"[UNSAFE] Consumed: {item} | Shelf: {self.items} | Size: {len(self.items)}")
        self._report("consumed", item)
        return item