import threading
from buffer import Buffer
from producer import producer
from consumer import consumer

if __name__ == "__main__":
    NUM_ITEMS = 8       # how many items to produce/consume
    SHELF_CAPACITY = 3  # how many items the shelf can hold at once

    shelf = Buffer(SHELF_CAPACITY)

    producer_thread = threading.Thread(target=producer, args=(shelf, NUM_ITEMS))
    consumer_thread = threading.Thread(target=consumer, args=(shelf, NUM_ITEMS))

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join()
    consumer_thread.join()

    print("All done! Producer and consumer finished successfully.")