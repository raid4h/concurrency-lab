import threading
import time
import random


class RWState:
    """Shared state for the Readers-Writers demo."""

    def __init__(self):
        self.document_version = 0
        self.readcount = 0  # part of the classic algorithm, protected by mutex

        # Semaphores exactly as taught in the textbook solution (Ch.6, slides 27-28)
        self.mutex = threading.Semaphore(1)   # protects readcount
        self.wrt = threading.Semaphore(1)     # grants exclusive write access

        # Instrumentation only (not part of the algorithm) — used to detect
        # violations for the unsafe demo and drive the GUI. Protected separately
        # so the measurement itself doesn't introduce a fake race condition.
        self._stats_lock = threading.Lock()
        self.active_readers = 0
        self.active_writers = 0
        self.violation_count = 0

    def mark_reader_start(self, event_queue, reader_id):
        with self._stats_lock:
            self.active_readers += 1
            violation = self.active_writers > 0
            if violation:
                self.violation_count += 1
            if event_queue:
                event_queue.put({"type": "rw_event", "role": "reader", "id": reader_id,
                                  "action": "reading", "document": self.document_version,
                                  "violation": violation})

    def mark_reader_end(self, event_queue, reader_id):
        with self._stats_lock:
            self.active_readers -= 1
            if event_queue:
                event_queue.put({"type": "rw_event", "role": "reader", "id": reader_id,
                                  "action": "idle", "document": self.document_version,
                                  "violation": False})

    def mark_writer_start(self, event_queue, writer_id):
        with self._stats_lock:
            self.active_writers += 1
            violation = self.active_writers > 1 or self.active_readers > 0
            if violation:
                self.violation_count += 1
            if event_queue:
                event_queue.put({"type": "rw_event", "role": "writer", "id": writer_id,
                                  "action": "writing", "document": self.document_version,
                                  "violation": violation})

    def mark_writer_end(self, event_queue, writer_id):
        with self._stats_lock:
            self.document_version += 1
            self.active_writers -= 1
            if event_queue:
                event_queue.put({"type": "rw_event", "role": "writer", "id": writer_id,
                                  "action": "idle", "document": self.document_version,
                                  "violation": False})


def reader_task(state, reader_id, iterations, safe_mode, event_queue):
    for _ in range(iterations):
        time.sleep(random.uniform(0.2, 0.5))

        if safe_mode:
            state.mutex.acquire()
            state.readcount += 1
            if state.readcount == 1:
                state.wrt.acquire()  # first reader locks out writers
            state.mutex.release()

        state.mark_reader_start(event_queue, reader_id)
        time.sleep(random.uniform(0.3, 0.6))  # simulate reading
        state.mark_reader_end(event_queue, reader_id)

        if safe_mode:
            state.mutex.acquire()
            state.readcount -= 1
            if state.readcount == 0:
                state.wrt.release()  # last reader lets writers back in
            state.mutex.release()

    if event_queue:
        event_queue.put({"type": "rw_finished", "role": "reader", "id": reader_id})


def writer_task(state, writer_id, iterations, safe_mode, event_queue):
    for _ in range(iterations):
        time.sleep(random.uniform(0.3, 0.7))

        if safe_mode:
            state.wrt.acquire()

        state.mark_writer_start(event_queue, writer_id)
        time.sleep(random.uniform(0.4, 0.7))  # simulate writing
        state.mark_writer_end(event_queue, writer_id)

        if safe_mode:
            state.wrt.release()

    if event_queue:
        event_queue.put({"type": "rw_finished", "role": "writer", "id": writer_id})


def run_readers_writers(num_readers, num_writers, iterations, safe_mode, event_queue):
    state = RWState()
    threads = []

    for i in range(num_readers):
        threads.append(threading.Thread(target=reader_task,
                                          args=(state, i, iterations, safe_mode, event_queue)))
    for i in range(num_writers):
        threads.append(threading.Thread(target=writer_task,
                                          args=(state, i, iterations, safe_mode, event_queue)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if event_queue:
        event_queue.put({"type": "rw_done", "violation_count": state.violation_count})