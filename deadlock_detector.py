"""
Implements deadlock DETECTION (Ch.7, wait-for graph + cycle search) and
RECOVERY (Ch.7, "Recovery from Deadlock") together: a background thread
maintains a live wait-for graph, searches it for cycles via DFS, and the
moment a cycle is found, immediately triggers recovery by forcibly
preempting a resource from a chosen 'victim' philosopher and terminating
that philosopher's thread of execution - breaking the cycle so the
remaining philosophers can finish normally.

This reuses the Dining Philosophers scenario (5 philosophers, 5 forks)
but instruments it so a background thread can see, in real time, who
is waiting on whom - then runs real cycle-detection AND recovery
algorithms on that data, rather than just reporting a timeout.
"""

import threading
import time
import random


class PhilosopherAborted(Exception):
    """
    Raised inside a philosopher's own thread to unwind it out of its
    main loop the moment it's been marked as a recovery 'victim'.
    Python provides no safe way to forcibly kill a thread from the
    outside, so termination has to be COOPERATIVE: the philosopher's
    own acquire loop periodically checks whether it's been marked for
    termination, and raises this itself to exit voluntarily.
    """
    pass


class InstrumentedFork:
    """
    A single fork (a 'resource' in OS terms). Just like a normal Lock,
    but we also track WHO currently holds it, so the detector/recovery
    system can see exactly who owns what at any moment.
    """
    def __init__(self, fork_id):
        self.fork_id = fork_id
        self.lock = threading.Lock()  # the REAL mutual-exclusion mechanism
        self.owner = None             # bookkeeping only: which philosopher holds this fork right now


class DetectorState:
    """
    Shared bookkeeping between all philosopher threads, the detector
    thread, and the recovery logic.
    """
    def __init__(self, num_philosophers):
        # waiting_for[i] = the fork_id philosopher i is currently BLOCKED on,
        # or None if philosopher i isn't waiting for anything right now.
        self.waiting_for = {i: None for i in range(num_philosophers)}

        # Protects reads/writes to waiting_for and aborted, so the
        # detector thread never reads them mid-update from a philosopher.
        self.lock = threading.Lock()

        self.stop_detector = threading.Event()  # signal to stop the detector thread
        self.cycle_found = None                 # the FIRST cycle detected, kept for reporting

        # Philosopher ids forcibly terminated by recovery to break a
        # deadlock. Checked by each philosopher's own acquire loop so
        # it knows to give up.
        self.aborted = set()


def build_wait_for_graph(state, forks):
    """
    Builds the wait-for graph: a dict {philosopher_id: philosopher_id_they_wait_on}.
    Ch.7: "Pi -> Pj if Pi is waiting for Pj" - here, "waiting for a
    fork" becomes "waiting for whoever currently holds that fork."
    """
    graph = {}
    with state.lock:  # briefly lock so we get a consistent snapshot
        for phil_id, waiting_fork_id in state.waiting_for.items():
            if waiting_fork_id is None:
                graph[phil_id] = None  # this philosopher isn't blocked right now
            else:
                graph[phil_id] = forks[waiting_fork_id].owner
    return graph


def detect_cycle(graph):
    """
    Classic cycle-detection over a wait-for graph where every node has
    AT MOST one outgoing edge. Follows 'waiting on' edges one at a
    time; landing on a node already in the current path means we've
    found a loop - the deadlock cycle itself.

    Returns: list of philosopher IDs forming the cycle, or None.
    """
    visited = set()

    for start in graph:
        if start in visited:
            continue

        path = []
        path_index = {}
        node = start

        while node is not None and node not in visited:
            if node in path_index:
                cycle_start = path_index[node]
                return path[cycle_start:]

            path_index[node] = len(path)
            path.append(node)
            node = graph.get(node)

        visited.update(path)

    return None


def _select_victim(cycle, state):
    """
    Chooses which philosopher to terminate to break a detected cycle.
    Real recovery systems weigh factors like process priority, how
    much computation would be lost, and how many resources are held
    (Ch.7, "Recovery from Deadlock: Selecting a Victim"). We use the
    simplest such factor: always terminate the LOWEST-ID philosopher
    in the cycle that hasn't already been terminated - deterministic
    and easy to explain in a demo.
    """
    candidates = [p for p in cycle if p not in state.aborted]
    if not candidates:
        return None  # everyone in this cycle has already been dealt with
    return min(candidates)


def _recover_from_cycle(state, forks, cycle, event_queue):
    """
    RECOVERY: forcibly breaks a confirmed deadlock cycle via PROCESS
    TERMINATION - pick a victim, take away whatever resource it
    currently holds, and permanently stop that philosopher's thread
    from making further progress. This is functionally the same
    response MySQL's InnoDB engine gives when ITS OWN wait-for-graph
    detector finds a real deadlock: pick a victim transaction and
    roll it back so the others can proceed.
    """
    victim = _select_victim(cycle, state)
    if victim is None:
        return  # nothing left to recover in this cycle

    # Find whichever fork the victim currently HOLDS (its first-
    # acquired fork, not the one it's blocked waiting for).
    held_fork = None
    for fork in forks:
        if fork.owner == victim:
            held_fork = fork
            break

    if held_fork is None:
        return  # victim isn't holding anything yet - nothing to preempt this round

    # THE ACTUAL PREEMPTION: forcibly take the fork back, without the
    # victim's cooperation. Python's plain threading.Lock does not
    # track which thread owns it, so release() may legally be called
    # from ANY thread - this is what makes forced preemption possible.
    held_fork.owner = None
    held_fork.lock.release()

    with state.lock:
        state.aborted.add(victim)  # the victim's own thread checks this and gives up

    if event_queue:
        event_queue.put({
            "type": "recovery_action",
            "victim": victim,
            "freed_fork": held_fork.fork_id
        })


def detector_thread_func(state, forks, event_queue, poll_interval=0.3):
    """
    Runs continuously in the background. Every poll_interval seconds:
    rebuilds the wait-for graph, checks it for a cycle, and - if one
    is found - immediately triggers recovery to break it. Keeps
    monitoring afterward (rather than stopping at the first cycle),
    since recovery is meant to be a repeatable response, not a
    one-time event.
    """
    while not state.stop_detector.is_set():
        graph = build_wait_for_graph(state, forks)
        cycle = detect_cycle(graph)

        if event_queue:
            event_queue.put({"type": "graph_snapshot", "graph": graph, "cycle": cycle})

        if cycle:
            if state.cycle_found is None:
                state.cycle_found = cycle  # remember the FIRST cycle, for the final report
                if event_queue:
                    event_queue.put({"type": "cycle_detected", "cycle": cycle})

            _recover_from_cycle(state, forks, cycle, event_queue)

        time.sleep(poll_interval)


class DetectorPhilosopher(threading.Thread):
    """
    Same idea as the Philosopher class in philosophers.py, but
    instrumented so DetectorState always knows what each philosopher
    is waiting for, AND so recovery can forcibly terminate it.
    """
    def __init__(self, phil_id, left_fork, right_fork, state, safe_mode, meals_target=3):
        super().__init__()
        self.phil_id = phil_id
        self.left_fork = left_fork
        self.right_fork = right_fork
        self.state = state
        self.safe_mode = safe_mode
        self.meals_target = meals_target
        self.finished = False  # only ever set True if this philosopher completed normally

    def _acquire_fork(self, fork):
        # Record that we're ABOUT to try for this fork, before the
        # actual attempt, so the detector can see us waiting even
        # while we're blocked.
        with self.state.lock:
            self.state.waiting_for[self.phil_id] = fork.fork_id

        # POLL with a short timeout instead of blocking forever. This
        # is what makes cooperative termination possible: a single
        # blocking acquire() call could never be interrupted once
        # entered, so we retry in a loop, checking after every failed
        # attempt whether recovery has marked us for termination.
        while True:
            if self.phil_id in self.state.aborted:
                raise PhilosopherAborted()

            got_it = fork.lock.acquire(timeout=0.2)
            if got_it:
                break

        fork.owner = self.phil_id
        with self.state.lock:
            self.state.waiting_for[self.phil_id] = None

    def _release_fork(self, fork):
        fork.owner = None
        fork.lock.release()

    def run(self):
        meals = 0
        try:
            while meals < self.meals_target:
                time.sleep(random.uniform(0.2, 0.5))  # thinking

                if self.safe_mode:
                    # SAFE: always grab the lower-numbered fork first
                    # (deadlock PREVENTION - breaks circular wait).
                    first, second = (self.left_fork, self.right_fork) \
                        if self.left_fork.fork_id < self.right_fork.fork_id \
                        else (self.right_fork, self.left_fork)
                else:
                    # UNSAFE: always left-then-right - this is what CAN
                    # deadlock, and what recovery exists to clean up after.
                    first, second = self.left_fork, self.right_fork

                self._acquire_fork(first)
                time.sleep(random.uniform(0.1, 0.3))  # gives a deadlock time to actually form
                self._acquire_fork(second)

                time.sleep(random.uniform(0.2, 0.4))  # eating
                meals += 1

                self._release_fork(second)
                self._release_fork(first)

            self.finished = True  # only reached by philosophers who were never terminated

        except PhilosopherAborted:
            # This philosopher was forcibly terminated by recovery to
            # break a deadlock. Deliberately does NOT set self.finished,
            # and does not try to acquire or release anything further -
            # this is what lets downstream reporting correctly tell a
            # recovery victim apart from a philosopher that simply
            # never got a chance to run.
            pass


def run_detection_demo(num_philosophers, safe_mode, event_queue):
    """
    Sets up philosophers + forks + the background detector/recovery
    system, runs everything, and reports the final outcome.
    """
    forks = [InstrumentedFork(i) for i in range(num_philosophers)]
    state = DetectorState(num_philosophers)

    philosophers = []
    for i in range(num_philosophers):
        left = forks[i]
        right = forks[(i + 1) % num_philosophers]
        p = DetectorPhilosopher(i, left, right, state, safe_mode)
        p.daemon = True  # ensures the app can still exit even if a philosopher never finishes
        philosophers.append(p)

    detector = threading.Thread(target=detector_thread_func,
                                  args=(state, forks, event_queue), daemon=True)
    detector.start()

    for p in philosophers:
        p.start()

    # Give philosophers a bounded amount of time to finish. With
    # recovery active, an unsafe run should now typically finish well
    # within this window instead of hanging for the full duration.
    for p in philosophers:
        p.join(timeout=8)

    state.stop_detector.set()  # tell the detector loop to stop polling
    detector.join(timeout=2)

    stuck = [p.phil_id for p in philosophers if not p.finished]
    victims = sorted(state.aborted)  # who recovery actually terminated

    if event_queue:
        event_queue.put({
            "type": "detection_done",
            "cycle": state.cycle_found,
            "stuck": stuck,
            "victims": victims
        })