from logger import init_db, log_run, get_all_runs

init_db()

# Insert a couple of fake test entries
log_run("producer_consumer", "safe", duration_seconds=2.3, violation_count=0)
log_run("producer_consumer", "unsafe", duration_seconds=1.8, violation_count=4)
log_run("dining_philosophers", "safe", duration_seconds=5.1, deadlock_detected=0)
log_run("dining_philosophers", "unsafe", duration_seconds=8.0, deadlock_detected=1)

print("All logged runs:")
for row in get_all_runs():
    print(row)