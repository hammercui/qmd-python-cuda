import psutil

print("Checking qmd processes...")
procs = []
for proc in psutil.process_iter(['name', 'cmdline']):
    try:
        cmdline_list = proc.info.get('cmdline')
        if not cmdline_list:
            continue
        cmdline = ' '.join(cmdline_list)
        if 'qmd' in cmdline:
            procs.append(proc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print(f"Found {len(procs)} qmd processes")
for p in procs[:10]:
    cmdline = ' '.join(p.info.get('cmdline', [])[:10])
    print(f"  PID {p.pid}: {cmdline[:80]}")
