"""
Implements deadlock DETECTION (as opposed to prevention):
"Maintain wait-for graph... periodically invoke an
algorithm that searches for a cycle. If there is a cycle, there is a deadlock."

This reuses the Dining Philosophers scenario (5 philosophers, 5 forks) but
instruments it so a background thread can see, in real time, who is
waiting on whom - then runs a real cycle-detection algorithm on that data.
"""

import threading
import time
import random


class InstrumentedFork:
    """
    A single fork (a 'resource' in OS terms). Just like a normal Lock,
    but we also track WHO currently holds it, so the detector thread
    can build the wait-for graph later.
    """
    def __init__(self, fork_id):
        self.fork_id = fork_id
        self.lock = threading.Lock()  # the REAL mutual-exclusion mechanism
        self.owner = None             # bookkeeping only: which philosopher holds this fork right now


class DetectorState:
    """
    Shared bookkeeping between all philosopher threads and the detector thread.
    """
    def __init__(self, num_philosophers):
        # waiting_for[i] = the fork_id philosopher i is currently BLOCKED on,
        # or None if philosopher i isn't waiting for anything right now.
        self.waiting_for = {i: None for i in range(num_philosophers)}

        # Protects reads/writes to the waiting_for dict above, so the detector
        # thread never reads it while a philosopher thread is mid-update.
        self.lock = threading.Lock()

        self.stop_detector = threading.Event()  # signal to tell the detector thread to stop
        self.cycle_found = None                 # will hold the list of philosophers in a cycle, if any


def build_wait_for_graph(state, forks):
    """
    Builds the wait-for graph: a dict {philosopher_id: philosopher_id_they_wait_on}.
    This is exactly Ch.7 slide 34's "Pi -> Pj if Pi is waiting for Pj" -
    here, "waiting for a fork" becomes "waiting for whoever holds that fork."
    """
    graph = {}
    with state.lock:  # briefly lock so we get a consistent snapshot of waiting_for
        for phil_id, waiting_fork_id in state.waiting_for.items():
            if waiting_fork_id is None:
                graph[phil_id] = None  # this philosopher isn't blocked right now
            else:
                # Find out who currently owns the fork this philosopher is stuck on.
                # NOTE: reading fork.owner here without a lock is a deliberate,
                # documented simplification - a real detector also tolerates
                # slightly-stale snapshots, since it just re-polls again shortly after.
                graph[phil_id] = forks[waiting_fork_id].owner
    return graph


def detect_cycle(graph):
    """
    Classic cycle-detection over a wait-for graph where every node has AT MOST
    one outgoing edge (a philosopher can only be actively blocked on one fork
    at a time). This is the algorithm behind Ch.7 slide 34.

    How it works: starting from each unvisited node, follow the "waiting on"
    edges one at a time. If we ever land on a node that's already in OUR
    current path, we've found a loop - that loop is the deadlock cycle.

    Returns: list of philosopher IDs forming the cycle, or None if no cycle exists.
    """
    visited = set()  # nodes fully explored in a previous outer-loop pass; skip re-checking them

    for start in graph:
        if start in visited:
            continue  # already know this node doesn't lead to a cycle

        path = []        # the chain of nodes visited on this particular pass, in order
        path_index = {}  # maps node -> its position in 'path' (for instant cycle detection)
        node = start

        while node is not None and node not in visited:
            if node in path_index:
                # We've looped back to a node already on our current path: that's the cycle.
                cycle_start = path_index[node]
                return path[cycle_start:]

            path_index[node] = len(path)
            path.append(node)
            node = graph.get(node)  # follow the edge to the next node

        visited.update(path)  # mark everything on this pass as fully explored

    return None  # went through every node with no repeats found: no deadlock


def detector_thread_func(state, forks, event_queue, poll_interval=0.3):
    """
    Runs continuously in the background while philosophers are thinking/eating/waiting.
    Every `poll_interval` seconds, rebuild the graph and check it for a cycle.
    Mirrors slide 41: "How often to invoke [detection] depends on how often
    a deadlock is likely to occur."
    """
    while not state.stop_detector.is_set():
        graph = build_wait_for_graph(state, forks)
        cycle = detect_cycle(graph)

        # Send the current graph snapshot to the GUI so it can redraw the picture live
        if event_queue:
            event_queue.put({"type": "graph_snapshot", "graph": graph, "cycle": cycle})

        if cycle:
            state.cycle_found = cycle
            if event_queue:
                event_queue.put({"type": "cycle_detected", "cycle": cycle})
            break  # deadlock confirmed - no need to keep polling

        time.sleep(poll_interval)


class DetectorPhilosopher(threading.Thread):
    """
    Same idea as the Philosopher class in philosophers.py, but instrumented
    so DetectorState always knows exactly what each philosopher is waiting for.
    """
    def __init__(self, phil_id, left_fork, right_fork, state, safe_mode, meals_target=3):
        super().__init__()
        self.phil_id = phil_id
        self.left_fork = left_fork
        self.right_fork = right_fork
        self.state = state
        self.safe_mode = safe_mode
        self.meals_target = meals_target
        self.finished = False  # lets the caller check who did/didn't finish afterward

    def _acquire_fork(self, fork):
        # Step 1: record that we're ABOUT to block trying to get this fork.
        # This must happen BEFORE the actual (possibly blocking) acquire() call,
        # so the detector can see we're waiting even while we're stuck.
        with self.state.lock:
            self.state.waiting_for[self.phil_id] = fork.fork_id

        fork.lock.acquire()  # <-- this line can block indefinitely if deadlocked

        # Step 2: we got it. Record ownership, and clear our "waiting" status.
        fork.owner = self.phil_id
        with self.state.lock:
            self.state.waiting_for[self.phil_id] = None

    def _release_fork(self, fork):
        fork.owner = None
        fork.lock.release()

    def run(self):
        meals = 0
        while meals < self.meals_target:
            time.sleep(random.uniform(0.2, 0.5))  # thinking

            if self.safe_mode:
                # SAFE: always grab the lower-numbered fork first.
                # This is deadlock PREVENTION (breaks "circular wait", Ch.7 slide 15).
                first, second = (self.left_fork, self.right_fork) \
                    if self.left_fork.fork_id < self.right_fork.fork_id \
                    else (self.right_fork, self.left_fork)
            else:
                # UNSAFE: always left-then-right - this is what CAN cause deadlock.
                first, second = self.left_fork, self.right_fork

            self._acquire_fork(first)
            time.sleep(random.uniform(0.1, 0.3))  # gives a deadlock time to actually form
            self._acquire_fork(second)

            time.sleep(random.uniform(0.2, 0.4))  # eating
            meals += 1

            self._release_fork(second)
            self._release_fork(first)

        self.finished = True  # only reached if this philosopher was never stuck forever


def run_detection_demo(num_philosophers, safe_mode, event_queue):
    """
    Sets up philosophers + forks + the background detector, runs everything,
    and reports the final outcome once philosophers finish (or time out).
    """
    forks = [InstrumentedFork(i) for i in range(num_philosophers)]
    state = DetectorState(num_philosophers)

    philosophers = []
    for i in range(num_philosophers):
        left = forks[i]
        right = forks[(i + 1) % num_philosophers]
        p = DetectorPhilosopher(i, left, right, state, safe_mode)
        p.daemon = True  # so a truly deadlocked thread can't prevent the app from closing later
        philosophers.append(p)

    # Start the detector FIRST so it's watching from the very first moment.
    detector = threading.Thread(target=detector_thread_func,
                                  args=(state, forks, event_queue), daemon=True)
    detector.start()

    for p in philosophers:
        p.start()

    # Give philosophers a bounded amount of time to finish naturally.
    # If truly deadlocked, some will simply never finish - that's expected,
    # and the daemon=True flag above ensures this doesn't hang the whole app.
    for p in philosophers:
        p.join(timeout=8)

    state.stop_detector.set()  # tell the detector loop to stop polling
    detector.join(timeout=2)

    stuck = [p.phil_id for p in philosophers if not p.finished]

    if event_queue:
        event_queue.put({
            "type": "detection_done",
            "cycle": state.cycle_found,
            "stuck": stuck
        })