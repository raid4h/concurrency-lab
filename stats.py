"""
Builds the matplotlib Figure used in the Performance Stats tab.
Reads every logged demo run from the SQLite database and produces
one bar chart per metric, comparing 'safe' vs 'unsafe' runs.

DESIGN NOTES:
- Every bar gets a numeric label directly above it (even "0"), so a
  correctly-zero safe run doesn't look like missing/broken data.
- The first chart (10 bars across all 5 demo types) has its x-axis
  labels rotated 40°, since 10 horizontal labels side-by-side collide.
"""

from matplotlib.figure import Figure
from logger import get_all_runs

# Short display labels for each (demo_type, mode) pair, shown on chart 1's x-axis
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

# The order demo types appear on the duration chart
DEMO_TYPES = [
    "producer_consumer",
    "dining_philosophers",
    "multiprocess_counter",
    "readers_writers",
    "deadlock_detection",
]


def _bar_with_labels(ax, x_labels, values, colors, title):
    """
    Draws a bar chart with a numeric label ABOVE every bar (even ones
    with height 0), and guarantees the y-axis always has some visible
    headroom so those labels are never clipped.
    """
    bars = ax.bar(x_labels, values, color=colors)

    # Force some y-axis height even when every value is 0 - otherwise
    # matplotlib's auto-range can be [0, 0], which renders unpredictably.
    max_value = max(values) if values else 0
    ax.set_ylim(0, max(max_value * 1.3, 1))

    # Writes the actual number just above each bar, so "0" is always
    # clearly readable text, not just an absent/invisible bar.
    ax.bar_label(bars, padding=3, fontsize=8)

    ax.set_title(title, fontsize=10)
    return bars


def build_stats_figure():
    """Reads all logged runs and builds a Figure with 6 stacked bar charts."""
    rows = get_all_runs()  # each row: (demo_type, mode, duration, violations, deadlock, timestamp)

    # constrained_layout auto-spaces subplots/titles based on rendered text size.
    fig = Figure(figsize=(6.0, 15.5), dpi=100, constrained_layout=True)
    fig.patch.set_facecolor("#fbfbf6")  # match the app's card background

    # Give extra vertical breathing room between subplots (hspace) - this is
    # what stops chart 1's ROTATED bottom labels from bumping into chart 2's
    # title, which sits directly beneath it.
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.04, hspace=0.16, wspace=0.05)

    if not rows:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No data yet.\nRun some demos first!",
                 ha="center", va="center", fontsize=12)
        ax.axis("off")
        return fig

    # --- accumulate totals across every logged run ---
    duration_sums = {}
    duration_counts = {}
    pc_violation_totals = {"safe": 0, "unsafe": 0}
    dp_deadlock_totals = {"safe": 0, "unsafe": 0}
    mp_lost_totals = {"safe": 0, "unsafe": 0}
    rw_violation_totals = {"safe": 0, "unsafe": 0}
    dd_cycle_totals = {"safe": 0, "unsafe": 0}

    for demo_type, mode, duration, violations, deadlock, ts in rows:
        key = (demo_type, mode)
        duration_sums[key] = duration_sums.get(key, 0) + duration
        duration_counts[key] = duration_counts.get(key, 0) + 1

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

    avg_durations = {k: duration_sums[k] / duration_counts[k] for k in duration_sums}

    # --- Chart 1: average duration per demo/mode (10 bars - needs rotated labels) ---
    ax1 = fig.add_subplot(611)
    labels, values, colors = [], [], []
    for demo_type in DEMO_TYPES:
        for mode in ["safe", "unsafe"]:
            key = (demo_type, mode)
            if key in avg_durations:
                labels.append(LABELS[key])
                values.append(round(avg_durations[key], 2))
                colors.append("#6a994e" if mode == "safe" else "#bc4749")

    _bar_with_labels(ax1, labels, values, colors, "Average Run Duration (seconds)")

    # Rotate the 10 x-axis labels 40° and right-align them, so they no
    # longer sit shoulder-to-shoulder and collide with each other.
    for tick_label in ax1.get_xticklabels():
        tick_label.set_rotation(40)
        tick_label.set_ha("right")   # "right" keeps each label's end near its own bar
        tick_label.set_fontsize(7.5)

    # --- Chart 2: Producer-Consumer capacity violations (only 2 bars, no rotation needed) ---
    ax2 = fig.add_subplot(612)
    _bar_with_labels(
        ax2, ["Safe", "Unsafe"],
        [pc_violation_totals.get("safe", 0), pc_violation_totals.get("unsafe", 0)],
        ["#6a994e", "#bc4749"],
        "Total Capacity Violations (Producer-Consumer)"
    )

    # --- Chart 3: Dining Philosophers deadlocks (via timeout) ---
    ax3 = fig.add_subplot(613)
    _bar_with_labels(
        ax3, ["Safe", "Unsafe"],
        [dp_deadlock_totals.get("safe", 0), dp_deadlock_totals.get("unsafe", 0)],
        ["#6a994e", "#bc4749"],
        "Deadlocks Detected (Dining Philosophers)"
    )

    # --- Chart 4: Multi-process lost updates ---
    ax4 = fig.add_subplot(614)
    _bar_with_labels(
        ax4, ["Safe", "Unsafe"],
        [mp_lost_totals.get("safe", 0), mp_lost_totals.get("unsafe", 0)],
        ["#6a994e", "#bc4749"],
        "Lost Updates (Multi-Process Counter)"
    )

    # --- Chart 5: Readers-Writers overlap violations ---
    ax5 = fig.add_subplot(615)
    _bar_with_labels(
        ax5, ["Safe", "Unsafe"],
        [rw_violation_totals.get("safe", 0), rw_violation_totals.get("unsafe", 0)],
        ["#6a994e", "#bc4749"],
        "Overlap Violations (Readers-Writers)"
    )

    # --- Chart 6: Cycles found by the wait-for graph detector ---
    ax6 = fig.add_subplot(616)
    _bar_with_labels(
        ax6, ["Safe", "Unsafe"],
        [dd_cycle_totals.get("safe", 0), dd_cycle_totals.get("unsafe", 0)],
        ["#6a994e", "#bc4749"],
        "Cycles Found by Detector (Wait-For Graph)"
    )

    return fig