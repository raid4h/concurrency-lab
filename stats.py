from matplotlib.figure import Figure
from logger import get_all_runs

LABELS = {
    ("producer_consumer", "safe"): "PC (safe)",
    ("producer_consumer", "unsafe"): "PC (unsafe)",
    ("dining_philosophers", "safe"): "DP (safe)",
    ("dining_philosophers", "unsafe"): "DP (unsafe)",
}


def build_stats_figure():
    """Builds a matplotlib Figure summarizing all logged demo runs."""
    rows = get_all_runs()
    # each row: (demo_type, mode, duration_seconds, violation_count, deadlock_detected, timestamp)

    fig = Figure(figsize=(6.5, 9.5), dpi=100, constrained_layout=True)
    fig.patch.set_facecolor("#fbfbf6")

    if not rows:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No data yet.\nRun some demos first!",
                 ha="center", va="center", fontsize=12)
        ax.axis("off")
        return fig

    duration_sums = {}
    duration_counts = {}
    violation_totals = {"safe": 0, "unsafe": 0}
    deadlock_totals = {"safe": 0, "unsafe": 0}

    for demo_type, mode, duration, violations, deadlock, ts in rows:
        key = (demo_type, mode)
        duration_sums[key] = duration_sums.get(key, 0) + duration
        duration_counts[key] = duration_counts.get(key, 0) + 1

        if demo_type == "producer_consumer":
            violation_totals[mode] = violation_totals.get(mode, 0) + (violations or 0)
        if demo_type == "dining_philosophers":
            deadlock_totals[mode] = deadlock_totals.get(mode, 0) + (deadlock or 0)

    avg_durations = {k: duration_sums[k] / duration_counts[k] for k in duration_sums}

    # --- Subplot 1: Average duration comparison ---
    ax1 = fig.add_subplot(311)
    labels, values, colors = [], [], []
    for demo_type in ["producer_consumer", "dining_philosophers"]:
        for mode in ["safe", "unsafe"]:
            key = (demo_type, mode)
            if key in avg_durations:
                labels.append(LABELS[key])
                values.append(avg_durations[key])
                colors.append("#6a994e" if mode == "safe" else "#bc4749")

    ax1.bar(labels, values, color=colors)
    ax1.set_title("Average Run Duration (seconds)", fontsize=10)
    ax1.tick_params(axis='x', labelsize=8)

    # --- Subplot 2: Race condition violations ---
    ax2 = fig.add_subplot(312)
    ax2.bar(["Safe", "Unsafe"],
            [violation_totals.get("safe", 0), violation_totals.get("unsafe", 0)],
            color=["#6a994e", "#bc4749"])
    ax2.set_title("Total Capacity Violations (Producer-Consumer)", fontsize=10)

    # --- Subplot 3: Deadlock occurrences ---
    ax3 = fig.add_subplot(313)
    ax3.bar(["Safe", "Unsafe"],
            [deadlock_totals.get("safe", 0), deadlock_totals.get("unsafe", 0)],
            color=["#6a994e", "#bc4749"])
    ax3.set_title("Deadlocks Detected (Dining Philosophers)", fontsize=10)

    return fig