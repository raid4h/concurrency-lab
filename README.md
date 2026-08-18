# Concurrency Lab

A Python desktop application that **demonstrates core Operating System concurrency concepts by actually reproducing them live**: race conditions, deadlock, and lost updates, rather than just describing them on slides.

**Demo video:** [link here]

## Why this project

Most beginner OS projects (task managers, file explorers, shell clones) are single-threaded utilities. ConcurrencyLab focuses specifically on the hardest, most misunderstood part of OS coursework: **process and thread synchronization**. Every tab shows a correct implementation alongside a deliberately broken one, so the bug being prevented is visible, not theoretical.

## What it covers

| Tab | Concept | Maps to |
|---|---|---|
| **Producer–Consumer** | Bounded buffer, race conditions | Classical Synchronization Problem #1 |
| **Dining Philosophers** | Deadlock, prevention via resource ordering | Classical Synchronization Problem #2 |
| **Readers–Writers** | Explicit `threading.Semaphore`-based mutual exclusion | Classical Synchronization Problem #3 |
| **Multi-Process Counter** | Lost updates across real OS processes (not threads) | `multiprocessing.Value` / `multiprocessing.Lock` |
| **Deadlock Detector** | Live wait-for graph + DFS cycle detection | Deadlock *detection*, distinct from *prevention* |
| **File Processor** | Thread pool pattern on real files, measured speedup | Practical application of threading |
| **Performance Stats** | Aggregated results across many runs | Quantitative evidence, not one-off demos |

## Real-world parallels

- **Producer-Consumer** → message queues (Kafka, RabbitMQ), streaming buffers
- **Dining Philosophers** → database transaction managers negotiating table locks
- **Readers-Writers** → database read replicas vs. a single writer
- **Deadlock Detector** → MySQL's InnoDB engine detects deadlocks the same way: a wait-for graph, checked for cycles
- **File Processor** → cloud sync clients (Dropbox, Google Drive) uploading many files in parallel

## Tech stack

Built entirely on **Python's standard library** — `tkinter`, `sqlite3`, `threading`, `multiprocessing`. No pip installs required.

## How to run
git clone <https://github.com/raid4h/concurrency-lab> \
cd concurrency-lab \
python main.py 

That's it — no dependencies to install.

## Project structure
concurrency-lab/ \
├── main.py entry point \
├── config.py shared constants \
├── theme.py forest color theme, shared UI helpers \
├── gui/ one file per tab \
├── buffer.py, philosophers.py, multiproc_worker.py, \
│ readers_writers.py, deadlock_detector.py, file_processor.py \
│ the actual concurrency logic per demo \
├── logger.py, stats.py SQLite logging + aggregation \
├── test_*.py scripts used to verify race conditions/ \
│ deadlocks actually reproduce as intended 


