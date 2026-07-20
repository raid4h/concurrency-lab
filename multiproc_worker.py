import multiprocessing
import time


def increment_worker(counter, lock, process_id, increments, use_lock, mp_event_queue):
    """Runs inside a separate OS process. Increments the shared counter one at a time."""
    for i in range(increments):
        if use_lock:
            # SAFE: the lock ensures only one process can read+write the counter at a time
            with lock:
                current = counter.value
                time.sleep(0.001)  # simulated work, done *inside* the protected section
                counter.value = current + 1
        else:
            # UNSAFE: read and write are separate, unprotected steps.
            # Another process can sneak in between them and cause a lost update.
            current = counter.value
            time.sleep(0.001)
            counter.value = current + 1

        if mp_event_queue is not None and i % 5 == 0:
            mp_event_queue.put({
                "type": "process_progress",
                "id": process_id,
                "counter": counter.value
            })

    if mp_event_queue is not None:
        mp_event_queue.put({"type": "process_finished", "id": process_id})


def run_multiprocess_demo(num_processes, increments_per_process, use_lock, mp_event_queue):
    """Spawns real OS processes (not threads) that share one counter via shared memory."""
    counter = multiprocessing.Value('i', 0)   # 'i' = shared integer, lives in OS shared memory
    lock = multiprocessing.Lock()             # a lock that works ACROSS processes, not just threads

    processes = []
    for pid in range(num_processes):
        p = multiprocessing.Process(
            target=increment_worker,
            args=(counter, lock, pid, increments_per_process, use_lock, mp_event_queue)
        )
        processes.append(p)

    for p in processes:
        p.start()
    for p in processes:
        p.join()

    expected = num_processes * increments_per_process
    actual = counter.value

    if mp_event_queue is not None:
        mp_event_queue.put({
            "type": "process_done",
            "expected": expected,
            "actual": actual,
            "lost_updates": expected - actual
        })

    return expected, actual