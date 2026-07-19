from philosophers import run_philosophers

print("=== SAFE MODE ===")
run_philosophers(safe_mode=True)
print("Safe mode finished without deadlock.\n")

print("=== UNSAFE MODE (may deadlock) ===")
run_philosophers(safe_mode=False)
print("Unsafe mode test finished (check above — did any philosopher get stuck?).")