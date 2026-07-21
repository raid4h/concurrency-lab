"""
Aggregates every logged demo run from the SQLite database into plain
Python dictionaries/lists. This file has ZERO external dependencies -
just reads from logger.py. The actual drawing (turning these numbers
into bar charts) happens separately in gui/stats_tab.py using plain
Tkinter Canvas, so no charting library is needed anywhere in the app.
"""

from logger import get_all_runs

# Short display labels for each (demo_type, mode) pair, used on the duration chart
LABELS = {
    ("producer_consumer", "safe"): "PC (safe)",
    ("producer_consumer", "unsafe"): "PC (unsafe)",
    ("dining_philosophers", "safe"): "DP (safe)",
    ("dining_philosophers", "unsafe"): "DP (unsafe)",
    ("multiprocess_counter", "safe"): "MP (safe)",
    ("multiprocess_counter", "unsafe"): "MP (unsafe)",
    ("readers_writers", "safe"): "RW (safe)",
    ("readers_writers", "unsafe"): "RW (unsafe)",
    ("deadlock_detection", "safe"): "DD (safe)",
    ("deadlock_detection", "unsafe"): "DD (unsafe)",
}

# The order demo types should appear in on the duration chart
DEMO_TYPES = [
    "producer_consumer",
    "dining_philosophers",
    "multiprocess_counter",
    "readers_writers",
    "deadlock_detection",
]


def compute_stats():
    """
    Reads every logged run and returns a plain dict of aggregated
    numbers, ready for the GUI to hand-draw as bar charts. Returns
    None if no runs have been logged yet (so the GUI can show a
    friendly "no data" message instead of empty charts).
    """
    rows = get_all_runs()  # each row: (demo_type, mode, duration, violations, deadlock, timestamp)

    if not rows:
        return None  # nothing logged yet

    # --- running totals, built up one row at a time ---
    duration_sums = {}      # (demo_type, mode) -> total duration across all matching runs
    duration_counts = {}    # (demo_type, mode) -> how many matching runs contributed to that sum
    pc_violation_totals = {"safe": 0, "unsafe": 0}
    dp_deadlock_totals = {"safe": 0, "unsafe": 0}
    mp_lost_totals = {"safe": 0, "unsafe": 0}
    rw_violation_totals = {"safe": 0, "unsafe": 0}
    dd_cycle_totals = {"safe": 0, "unsafe": 0}

    for demo_type, mode, duration, violations, deadlock, ts in rows:
        key = (demo_type, mode)
        duration_sums[key] = duration_sums.get(key, 0) + duration
        duration_counts[key] = duration_counts.get(key, 0) + 1

        # Route each row's "violations"/"deadlock" count into the right bucket
        # depending on which demo type logged it.
        if demo_type == "producer_consumer":
            pc_violation_totals[mode] = pc_violation_totals.get(mode, 0) + (violations or 0)
        if demo_type == "dining_philosophers":
            dp_deadlock_totals[mode] = dp_deadlock_totals.get(mode, 0) + (deadlock or 0)
        if demo_type == "multiprocess_counter":
            mp_lost_totals[mode] = mp_lost_totals.get(mode, 0) + (violations or 0)
        if demo_type == "readers_writers":
            rw_violation_totals[mode] = rw_violation_totals.get(mode, 0) + (violations or 0)
        if demo_type == "deadlock_detection":
            dd_cycle_totals[mode] = dd_cycle_totals.get(mode, 0) + (deadlock or 0)

    # Convert running sums into per-run averages (total time / number of runs)
    avg_durations = {k: duration_sums[k] / duration_counts[k] for k in duration_sums}

    # Build the ordered list of {label, value, is_safe} entries for the duration chart
    duration_chart_data = []
    for demo_type in DEMO_TYPES:
        for mode in ["safe", "unsafe"]:
            key = (demo_type, mode)
            if key in avg_durations:  # only include combos that were actually run at least once
                duration_chart_data.append({
                    "label": LABELS[key],
                    "value": round(avg_durations[key], 2),
                    "is_safe": mode == "safe"
                })

    # Package everything into one dict the GUI can pull from directly
    return {
        "duration_chart": duration_chart_data,
        "pc_violations": pc_violation_totals,
        "dp_deadlocks": dp_deadlock_totals,
        "mp_lost_updates": mp_lost_totals,
        "rw_violations": rw_violation_totals,
        "dd_cycles": dd_cycle_totals,
    }