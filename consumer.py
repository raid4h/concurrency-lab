import time
import random

def consumer(buffer, num_items):
    for i in range(1, num_items + 1):
        time.sleep(random.uniform(0.5, 2.0))  # simulate time taken to "use" something
        item = buffer.get()
    print("Consumer finished consuming all items.")