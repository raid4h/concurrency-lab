import time
import random

def producer(buffer, num_items):
    for i in range(1, num_items + 1):
        item = f"item-{i}"
        time.sleep(random.uniform(0.5, 1.5))  # simulate time taken to "make" something
        buffer.put(item)
    print("Producer finished making all items.")