"""
A genuinely PRACTICAL concurrency application (unlike the other tabs,
which reproduce classic OS bugs): hashes every file in a real folder,
once sequentially and once with a thread pool, to measure real speedup.

The thread pool here reuses the exact same idea as the Producer-Consumer
tab - multiple worker threads pulling work items off ONE shared
queue.Queue - just applied to real files instead of a simulation.

Note on Python threading and the GIL: normally, Python's Global
Interpreter Lock means threads don't give real speedup for CPU-heavy
work. But file reads RELEASE the GIL while waiting on disk I/O, so
this is a legitimate, well-known case where plain threading (not
multiprocessing) provides genuine, measurable parallelism.
"""

import os
import hashlib
import threading
import queue
import time


def list_files(folder_path):
    """
    Returns a list of full file paths for every regular file directly
    inside folder_path. Deliberately NOT recursive (doesn't look inside
    subfolders), to keep runtime predictable and easy to explain.
    """
    entries = []
    for name in os.listdir(folder_path):
        full_path = os.path.join(folder_path, name)
        if os.path.isfile(full_path):  # skip subfolders, only count real files
            entries.append(full_path)
    return entries


def hash_file(path, chunk_size=65536):
    """
    Computes the MD5 checksum of one file, reading it in fixed-size
    chunks (64KB at a time) instead of loading the whole file into
    memory at once - standard practice, and matters for large files.
    """
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break  # reached end of file
            hasher.update(chunk)
    return hasher.hexdigest()


def process_sequential(file_paths, event_queue):
    """
    BASELINE: hashes every file ONE AT A TIME, on a single thread.
    This is what we're comparing the thread-pool version against below.
    """
    start = time.time()  # start the stopwatch

    for i, path in enumerate(file_paths):
        hash_file(path)  # the actual work - we don't need the digest itself here, just its cost

        if event_queue:
            # Report progress so the GUI can show "Hashed 3/12: filename.txt" live
            event_queue.put({
                "type": "file_progress", "mode": "sequential",
                "index": i, "total": len(file_paths),
                "filename": os.path.basename(path)
            })

    duration = time.time() - start  # stop the stopwatch

    if event_queue:
        event_queue.put({"type": "file_done", "mode": "sequential", "duration": duration})

    return duration


def process_thread_pool(file_paths, num_workers, event_queue):
    """
    Same hashing work as process_sequential(), but distributed across
    num_workers threads, all pulling from ONE shared queue.Queue.
    This is the "thread pool" pattern: pre-load all the work into a
    queue, spin up N workers, let them race to drain it.
    """
    start = time.time()

    # Pre-load every file path into a shared, thread-safe queue.
    # queue.Queue already handles all the locking internally - this is
    # the SAME class used inside the Buffer class in Producer-Consumer.
    work_queue = queue.Queue()
    for path in file_paths:
        work_queue.put(path)

    # Protects the shared 'completed' counter below, so two worker
    # threads never increment it at the exact same instant (which
    # would itself be a tiny race condition inside our own instrumentation).
    progress_lock = threading.Lock()
    completed = {"count": 0}

    def worker():
        """Runs on each of the num_workers threads. Keeps grabbing files
        from work_queue until it's empty, then exits."""
        while True:
            try:
                # get_nowait() raises queue.Empty the instant the queue
                # is drained - that's how each thread knows to stop.
                path = work_queue.get_nowait()
            except queue.Empty:
                return  # no files left - this worker's job is done

            hash_file(path)  # the actual work

            with progress_lock:
                completed["count"] += 1
                current_count = completed["count"]

            if event_queue:
                event_queue.put({
                    "type": "file_progress", "mode": "threadpool",
                    "index": current_count - 1, "total": len(file_paths),
                    "filename": os.path.basename(path)
                })

    # Create and start num_workers threads, all running the same worker() function
    threads = [threading.Thread(target=worker) for _ in range(num_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()  # wait for every worker thread to finish before measuring total time

    duration = time.time() - start

    if event_queue:
        event_queue.put({"type": "file_done", "mode": "threadpool", "duration": duration})

    return duration