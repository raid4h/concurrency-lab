import threading
from broken_buffer import BrokenBuffer
from producer import producer
from consumer import consumer

if __name__ == "__main__":
    NUM_ITEMS = 15
    SHELF_CAPACITY = 3

    shelf = BrokenBuffer(SHELF_CAPACITY)

    # Multiple producers and consumers to increase the chance of collision
    threads = []
    for i in range(3):
        threads.append(threading.Thread(target=producer, args=(shelf, NUM_ITEMS)))
    for i in range(3):
        threads.append(threading.Thread(target=consumer, args=(shelf, NUM_ITEMS)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("\nDone. Check above: did 'Size' ever exceed 3? That's the shelf capacity being violated!")