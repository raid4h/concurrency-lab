import threading
import time
import random


class Philosopher(threading.Thread):
    def __init__(self, name, left_fork, right_fork, event_queue=None, safe_mode=True, philosopher_id=0):
        super().__init__()
        self.name = name
        self.left_fork = left_fork
        self.right_fork = right_fork
        self.event_queue = event_queue
        self.safe_mode = safe_mode
        self.philosopher_id = philosopher_id
        self.running = True

    def _report(self, state):
        if self.event_queue:
            self.event_queue.put({
                "type": "philosopher",
                "id": self.philosopher_id,
                "name": self.name,
                "state": state
            })

    def run(self):
        meals = 0
        while self.running and meals < 3:
            self._report("thinking")
            time.sleep(random.uniform(0.3, 0.8))

            if self.safe_mode:
                # DEADLOCK-SAFE: always pick up the LOWER-numbered fork first.
                # This breaks the "circular wait" condition that causes deadlock.
                first, second = (self.left_fork, self.right_fork) \
                    if self.left_fork.fork_id < self.right_fork.fork_id \
                    else (self.right_fork, self.left_fork)
            else:
                # UNSAFE: always pick up left first, then right (can deadlock)
                first, second = self.left_fork, self.right_fork

            self._report("hungry")
            with first:
                self._report("picked_first_fork")
                time.sleep(random.uniform(0.1, 0.3))  # gives deadlock time to occur in unsafe mode
                with second:
                    self._report("eating")
                    time.sleep(random.uniform(0.3, 0.6))
                    meals += 1

            self._report("thinking")

        self._report("done")


class Fork:
    def __init__(self, fork_id):
        self.fork_id = fork_id
        self.lock = threading.Lock()

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()


def run_philosophers(event_queue=None, safe_mode=True, num_philosophers=5):
    forks = [Fork(i) for i in range(num_philosophers)]
    philosophers = []

    for i in range(num_philosophers):
        left_fork = forks[i]
        right_fork = forks[(i + 1) % num_philosophers]
        p = Philosopher(f"Philosopher-{i}", left_fork, right_fork,
                         event_queue=event_queue, safe_mode=safe_mode, philosopher_id=i)
        philosophers.append(p)

    for p in philosophers:
        p.start()

    for p in philosophers:
        p.join(timeout=8)  # timeout so an unsafe deadlock doesn't hang your program forever

    if event_queue:
        stuck = [p.name for p in philosophers if p.is_alive()]
        event_queue.put({"type": "philosopher_done", "stuck": stuck})