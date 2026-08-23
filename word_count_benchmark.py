"""
A genuinely PRACTICAL, non-simulated concurrency benchmark: counts word
frequencies across every text file in a real, user-chosen folder, using
three different execution strategies, and measures actual wall-clock
performance for each - real data, real work, real numbers.

Goes past the high-level threading/multiprocessing APIs used elsewhere
in this project to directly use two real OS-level system calls:

  - mmap.mmap(): memory-maps each file directly from disk instead of
    calling file.read(), letting the OS handle paging/caching rather
    than copying the whole file into a Python bytes object up front.

  - multiprocessing.Pipe(): a THIN wrapper directly over a real OS pipe
    (POSIX pipe()) or a real duplex socket (Windows) - used here
    instead of multiprocessing.Queue, which adds an internal background
    feeder thread on top of a pipe. Pipe() is closer to raw
    process-to-process IPC via the underlying system call.

This also demonstrates a genuine systems insight: because of Python's
Global Interpreter Lock (GIL), CPU-bound work like word counting sees
LITTLE speedup from threads (only one thread runs Python bytecode at a
time), but sees REAL, near-linear speedup from separate processes,
since each process has its own independent interpreter and GIL.
"""

import os
import re
import mmap
import time
import threading
import queue
import multiprocessing

# Matches sequences of alphabetic characters - our definition of "a
# word" for this benchmark. Deliberately simple/fast: the point is to
# measure concurrency overhead/speedup, not to build a perfect tokenizer.
WORD_PATTERN = re.compile(rb"[A-Za-z]+")


def list_text_files(folder_path, extensions=(".txt", ".py", ".md", ".csv", ".log")):
    """
    Returns full paths of files directly inside folder_path matching
    one of the given extensions. Restricting to text-like extensions
    avoids trying to word-count binary files, which would produce
    meaningless results.
    """
    paths = []
    for name in os.listdir(folder_path):
        full_path = os.path.join(folder_path, name)
        if os.path.isfile(full_path) and name.lower().endswith(extensions):
            paths.append(full_path)
    return paths


def count_words_in_file(path):
    """
    Counts word frequencies in ONE file using mmap() - a REAL system
    call - rather than file.read(). Memory-mapping the file lets the
    operating system page its contents in from disk on demand, instead
    of Python allocating one large bytes object and copying the file
    into it up front.
    """
    counts = {}

    with open(path, "rb") as f:
        # mmap.mmap() fails on a zero-length mapping, so empty files
        # need a guard here rather than attempting to map them.
        if os.fstat(f.fileno()).st_size == 0:
            return counts

        # access=mmap.ACCESS_READ: a read-only mapping, since this
        # benchmark never modifies file contents. Works identically on
        # Windows and POSIX with this keyword-argument form.
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            # re.finditer() can scan an mmap object DIRECTLY, since
            # mmap implements the buffer protocol - no separate read()
            # or copy is needed to search it.
            for match in WORD_PATTERN.finditer(mapped):
                word = match.group().lower()
                counts[word] = counts.get(word, 0) + 1

    return counts


def merge_counts(target, source):
    """Adds every count in 'source' into 'target', in place."""
    for word, n in source.items():
        target[word] = target.get(word, 0) + n


def top_words(counts, n=5):
    """Returns the n most frequent (word, count) pairs, for display."""
    return sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:n]


# ---------------------------------------------------------------------
# STRATEGY 1: Sequential (baseline)
# ---------------------------------------------------------------------

def run_sequential(file_paths, event_queue):
    """Counts every file ONE AT A TIME on a single thread - the
    baseline every other strategy is measured against."""
    start = time.time()
    total_counts = {}

    for i, path in enumerate(file_paths):
        merge_counts(total_counts, count_words_in_file(path))

        if event_queue:
            event_queue.put({
                "type": "progress", "mode": "sequential",
                "index": i, "total": len(file_paths),
                "filename": os.path.basename(path)
            })

    duration = time.time() - start

    if event_queue:
        event_queue.put({
            "type": "strategy_done", "mode": "sequential", "duration": duration,
            "total_words": sum(total_counts.values()), "top_words": top_words(total_counts)
        })

    return duration, total_counts


# ---------------------------------------------------------------------
# STRATEGY 2: Thread Pool (real OS threads + a real Lock)
# ---------------------------------------------------------------------

def run_thread_pool(file_paths, num_workers, event_queue):
    """
    Distributes files across num_workers REAL OS threads pulling from
    a shared queue.Queue. Each thread counts its own file locally (no
    locking needed there - it's private, per-thread work), then merges
    its result into ONE shared dict, protected by a single Lock kept
    as small as possible on purpose - a standard optimization: minimize
    time actually spent holding a lock.
    """
    start = time.time()

    work_queue = queue.Queue()
    for path in file_paths:
        work_queue.put(path)

    total_counts = {}
    merge_lock = threading.Lock()  # protects total_counts during merging ONLY
    progress_lock = threading.Lock()
    completed = {"count": 0}

    def worker():
        while True:
            try:
                path = work_queue.get_nowait()
            except queue.Empty:
                return  # no files left - this worker's job is done

            file_counts = count_words_in_file(path)  # local work, no lock needed

            with merge_lock:  # the ONLY section touching shared state
                merge_counts(total_counts, file_counts)

            with progress_lock:
                completed["count"] += 1
                current = completed["count"]

            if event_queue:
                event_queue.put({
                    "type": "progress", "mode": "threadpool",
                    "index": current - 1, "total": len(file_paths),
                    "filename": os.path.basename(path)
                })

    threads = [threading.Thread(target=worker) for _ in range(num_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    duration = time.time() - start

    if event_queue:
        event_queue.put({
            "type": "strategy_done", "mode": "threadpool", "duration": duration,
            "total_words": sum(total_counts.values()), "top_words": top_words(total_counts)
        })

    return duration, total_counts


# ---------------------------------------------------------------------
# STRATEGY 3: Multiprocessing (real OS processes + a real OS pipe)
# ---------------------------------------------------------------------

def _process_worker(file_paths_chunk, conn):
    """
    Runs inside a completely separate OS process. Counts words across
    its assigned chunk of files, then sends the result back to the
    parent process over 'conn' - one end of a multiprocessing.Pipe().
    """
    local_counts = {}
    for path in file_paths_chunk:
        merge_counts(local_counts, count_words_in_file(path))

    conn.send(local_counts)  # writes the result over the real OS pipe
    conn.close()


def run_multiprocess(file_paths, num_workers, event_queue):
    """
    Splits file_paths into num_workers roughly-equal chunks, spawns a
    REAL OS process per chunk, and collects each process's word counts
    back over a real multiprocessing.Pipe(). Because each process has
    its own independent Python interpreter (and therefore its own
    GIL), this is where genuine CPU-bound speedup becomes possible -
    unlike the thread pool above, which stays limited by ONE shared
    GIL across all its threads.
    """
    start = time.time()

    # Static partitioning up front - simpler across process boundaries
    # than sharing one queue.Queue the way the thread pool does.
    chunks = [file_paths[i::num_workers] for i in range(num_workers)]
    chunks = [c for c in chunks if c]  # drop empty chunks if fewer files than workers

    processes = []
    parent_conns = []

    for i, chunk in enumerate(chunks):
        # Pipe() returns TWO connected endpoints - one stays here in
        # the parent process, the other is handed to the child.
        parent_conn, child_conn = multiprocessing.Pipe()
        p = multiprocessing.Process(target=_process_worker, args=(chunk, child_conn))
        processes.append(p)
        parent_conns.append(parent_conn)
        p.start()

        if event_queue:
            event_queue.put({
                "type": "progress", "mode": "multiprocess",
                "index": i, "total": len(chunks),
                "filename": f"process {i} handling {len(chunk)} files"
            })

    total_counts = {}
    for conn in parent_conns:
        # .recv() blocks until the matching child calls .send() - a
        # real read on the real OS pipe/socket underneath.
        result = conn.recv()
        merge_counts(total_counts, result)
        conn.close()

    for p in processes:
        p.join()

    duration = time.time() - start

    if event_queue:
        event_queue.put({
            "type": "strategy_done", "mode": "multiprocess", "duration": duration,
            "total_words": sum(total_counts.values()), "top_words": top_words(total_counts)
        })

    return duration, total_counts