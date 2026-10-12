import sys, os
sys.path.insert(0, '.')
from collectors.system_memory import collect_system_memory, get_page_size
from collectors.process_memory import collect_process_memory

data = collect_system_memory()
print("=== System Memory ===")
print("Total RAM:    ", data["total_physical_mb"], "MiB")
print("Available:    ", data["available_physical_mb"], "MiB")
print("RAM %:        ", data["memory_percent"], "%")
print("Page size:    ", data["page_size_bytes"], "bytes")
print("System cache: ", data["system_cache_mb"], "MiB")
print("Commit total: ", data["commit_total_mb"], "MiB")
print("Processes:    ", data["process_count"])

pid = os.getpid()
info = collect_process_memory(pid)
print()
print("=== Process Memory (self, PID", pid, ") ===")
print("Name:        ", info["name"])
print("Working Set: ", info["working_set_mb"], "MiB")
print("Page Faults: ", info["page_fault_count"])
print("Private:     ", info["pagefile_usage_mb"], "MiB")
print("Error:       ", info["error"])

print()
print("Page size from get_page_size():", get_page_size())
print("All checks passed.")
