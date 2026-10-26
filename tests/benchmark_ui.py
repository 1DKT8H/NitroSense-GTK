"""Own preview window: measure visible and minimized CPU without hardware writes."""
import json
import resource
import time
import os
from pathlib import Path
from gi.repository import GLib
from nitrosense.app import NitroApplication

app = NitroApplication(preview=True)
app.set_application_id("io.github.nitrosense.Benchmark.p" + str(os.getpid()))
baseline = None


def counters():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return time.monotonic(), usage.ru_utime + usage.ru_stime


def start_sample():
    global baseline
    baseline = counters()
    return False


def report(label):
    now, cpu = counters()
    rss = next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:"))
    print(json.dumps({"state": label, "cpu_percent_one_core": round(100 * (cpu - baseline[1]) / (now - baseline[0]), 2),
                      "memory": rss, "active": app.window.is_active(),
                      "renderer": type(app.window.get_renderer()).__name__}), flush=True)
    if label == "visible":
        app.window.minimize()
    else:
        if os.environ.get("NITRO_BENCH_TRIM"):
            import gc, ctypes
            gc.collect()
            ctypes.CDLL(None).malloc_trim(0)
            print("After releasing unused heap:", next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("VmRSS:")), flush=True)
        app.window.close()
        app.quit()
    return False


def setup():
    app.poll()
    app.timer = GLib.timeout_add(500, app.poll)
    GLib.timeout_add_seconds(2, start_sample)
    GLib.timeout_add_seconds(10, lambda: report("visible"))
    GLib.timeout_add_seconds(30 if os.environ.get("NITRO_LONG_BENCH") else 12, start_sample)
    GLib.timeout_add_seconds(40 if os.environ.get("NITRO_LONG_BENCH") else 20, lambda: report("minimized"))
    return False


app.connect("activate", lambda *_: GLib.idle_add(setup))
app.run(["nitrosense-benchmark"])
