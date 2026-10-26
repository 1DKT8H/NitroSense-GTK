"""Minimal privileged backend. It accepts only a JSON object on stdin."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from contextlib import contextmanager

from .hardware import detect_profile
from .keyboard import apply_static, apply_effect


def fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}))
    raise SystemExit(1)


def write_ec(address: int, value: int) -> None:
    if not 0 <= value <= 255:
        fail("Invalid EC byte")
    for filename in ("/sys/kernel/debug/ec/ec0/io", "/dev/ec"):
        try:
            with open(filename, "r+b", buffering=0) as ec:
                ec.seek(address)
                ec.write(bytes((value,)))
            return
        except OSError:
            continue
    fail("No writable EC provider. Load ec_sys with write_support=1.")


def run_checked(argv: list[str]) -> None:
    if argv[0] == "undervolt":
        argv = [undervolt_binary(), *argv[1:]]
    if not shutil.which(argv[0]):
        fail(f"Required command unavailable: {argv[0]}")
    result = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=8)
    if result.returncode:
        fail(result.stderr.strip() or "Command rejected by driver/firmware")


def undervolt_binary():
    # Do not extend a root process PATH to user-controlled directories.
    for filename in ("/usr/bin/undervolt", "/usr/local/bin/undervolt"):
        path = Path(filename).resolve()
        try:
            chain = (path, *path.parents)
            if all(item.stat().st_uid == 0 and not item.stat().st_mode & 0o022 for item in chain) and os.access(path, os.X_OK):
                return str(path)
        except OSError:
            continue
    raise RuntimeError("A root-owned undervolt installation is required")


def progress(message):
    print(json.dumps({"progress": message}), flush=True)


@contextmanager
def voltage_lock():
    import fcntl
    with open("/run/nitrosense-voltage.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def perform(request: dict) -> dict | None:
    profile = detect_profile()
    action = request.get("action")
    if action == "fan":
        if not profile:
            fail("EC writes are disabled on an unverified model")
        target, speed = request.get("target"), request.get("speed")
        mode = request.get("mode", "manual")
        if target not in ("cpu", "gpu") or mode not in ("auto", "max", "manual"):
            fail("Invalid fan request")
        if mode == "manual":
            if type(speed) is not int or not 30 <= speed <= 100:
                fail("Manual fan speed must be between 30 and 100 percent")
            # AN515-55 reference writes level (0..20) * 5, i.e. a percentage,
            # NOT an 8-bit PWM value. Stage the speed before enabling manual.
            write_ec(profile.cpu_fan_speed if target == "cpu" else profile.gpu_fan_speed, speed)
        modes = {"cpu": {"auto": 0x04, "max": 0x08, "manual": 0x0C},
                 "gpu": {"auto": 0x10, "max": 0x20, "manual": 0x30}}
        write_ec(profile.cpu_fan_mode if target == "cpu" else profile.gpu_fan_mode, modes[target][mode])
    elif action == "coolboost":
        if not profile or not isinstance(request.get("enabled"), bool): fail("Invalid CoolBoost request")
        write_ec(profile.coolboost, 0x01 if request["enabled"] else 0x00)
    elif action == "charge_limit":
        if not profile or not isinstance(request.get("enabled"), bool): fail("Invalid charge-limit request")
        write_ec(profile.charge_limit, 0x71 if request["enabled"] else 0x31)
    elif action == "keyboard_timeout":
        if not profile or profile.keyboard_timeout is None or type(request.get("enabled")) is not bool:
            fail("Invalid keyboard timeout request")
        write_ec(profile.keyboard_timeout, 0x1e if request["enabled"] else 0x00)
    elif action == "keyboard":
        colour = request.get("colour", [])
        if not isinstance(colour, list) or len(colour) != 3: fail("Invalid keyboard colour")
        mode = request.get("mode", 0)
        if type(mode) is not int or mode not in range(6):
            fail("Invalid keyboard mode")
        if mode == 0:
            apply_static(int(request.get("zone", 0)), *(int(x) for x in colour), brightness=int(request.get("brightness", 100)))
        else:
            apply_effect(mode, request.get("speed", 4), request.get("brightness", 100), request.get("direction", 1), colour)
    elif action == "read_uv":
        from .voltage import read_offsets
        with voltage_lock():
            return read_offsets()
    elif action == "undervolt":
        core, cache = request.get("core_mv", request.get("mv")), request.get("cache_mv", request.get("mv"))
        if any(type(value) is not int or not -150 <= value <= 0 for value in (core, cache)):
            fail("Undervolt must be between -150 and 0 mV")
        with voltage_lock():
            run_checked(["undervolt", "--core", str(core), "--cache", str(cache)])
    elif action == "gpu_offset":
        offset = request.get("mhz")
        if not isinstance(offset, int) or not -300 <= offset <= 250: fail("GPU offset must be between -300 and +250 MHz")
        run_checked(["nvidia-settings", "-a", f"[gpu:0]/GPUGraphicsClockOffset[3]={offset}"])
    elif action == "gpu_memory_offset":
        offset = request.get("mhz")
        if type(offset) is not int or not -500 <= offset <= 1000:
            fail("Invalid VRAM offset")
        run_checked(["nvidia-settings", "-a", f"[gpu:0]/GPUMemoryTransferRateOffset[3]={offset}"])
    elif action == "cpu_turbo":
        value = request.get("enabled")
        if type(value) is not bool:
            fail("Invalid turbo request")
        Path("/sys/devices/system/cpu/intel_pstate/no_turbo").write_text("0" if value else "1")
    elif action == "cpu_performance":
        value = request.get("percent")
        if type(value) is not int or not 20 <= value <= 100:
            fail("CPU maximum performance must be between 20 and 100")
        Path("/sys/devices/system/cpu/intel_pstate/max_perf_pct").write_text(str(value))
    elif action == "cpu_epp":
        value = request.get("value")
        if value not in ("performance", "balance_performance", "balance_power", "power"):
            fail("Invalid EPP")
        paths = list(Path("/sys/devices/system/cpu/cpufreq").glob("policy*/energy_performance_preference"))
        if not paths:
            fail("EPP is unavailable")
        for path in paths:
            options = (path.parent / "energy_performance_available_preferences").read_text().split()
            if value not in options:
                fail("EPP is not supported")
        for path in paths:
            path.write_text(value)
    elif action == "cpu_power_limits":
        pl1, pl2 = request.get("pl1"), request.get("pl2")
        if not profile or type(pl1) is not int or type(pl2) is not int or not 10 <= pl1 <= 45 or not pl1 <= pl2 <= 90:
            fail("AN515-55: PL1 10..45 W, PL2 PL1..90 W")
        root = Path("/sys/class/powercap/intel-rapl:0")
        if (root / "name").read_text().strip() != "package-0":
            fail("Unexpected RAPL domain")
        # Confirm both interfaces before making changes.
        paths = [root / f"constraint_{i}_power_limit_uw" for i in (0, 1)]
        if not all(path.exists() for path in paths):
            fail("Power limits unavailable")
        if [(root / f"constraint_{i}_name").read_text().strip() for i in (0, 1)] != ["long_term", "short_term"]:
            fail("Unexpected RAPL constraint mapping")
        old = [path.read_text() for path in paths]
        try:
            for path, value in zip(paths, (pl1, pl2)):
                path.write_text(str(value * 1000000))
            actual = [int(path.read_text()) / 1e6 for path in paths]
            if any(abs(a - b) > .125 for a, b in zip(actual, (pl1, pl2))):
                raise OSError("Firmware did not retain the requested power limits")
        except OSError:
            for path, value in zip(paths, old):
                path.write_text(value)
            raise
    elif action == "cpu_power_window":
        seconds = request.get("seconds")
        if not profile or type(seconds) is not int or not 1 <= seconds <= 128:
            fail("Averaging window must be between 1 and 128 seconds")
        path = Path("/sys/class/powercap/intel-rapl:0/constraint_0_time_window_us")
        if (path.parent / "constraint_0_name").read_text().strip() != "long_term":
            fail("Unexpected RAPL constraint")
        path.write_text(str(seconds * 1000000))
    elif action == "install_rgb":
        if not profile:
            fail("RGB is only supported on AN515-55")
        progress("Budowanie modułu RGB dla kernela — może potrwać kilka minut…")
        result = subprocess.run(["dkms", "install", "-m", "nitrosense-rgb", "-v", "0.3.0"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode:
            fail((result.stderr or result.stdout)[-2000:])
        progress("Ładowanie modułu RGB…")
        run_checked(["modprobe", "nitrosense_rgb"])
    elif action in ("install_drivers", "install_overlay"):
        from .drivers import install_commands, overlay_install_commands
        commands = install_commands() if action == "install_drivers" else overlay_install_commands()
        for command in commands:
            progress("Odświeżanie listy pakietów…" if "update" in command else "Pobieranie i instalowanie pakietów…")
            result = subprocess.run(command, capture_output=True, text=True, timeout=900,
                                    env=dict(os.environ, DEBIAN_FRONTEND="noninteractive"))
            if result.returncode:
                fail((result.stderr or result.stdout)[-2000:])
    else:
        fail("Action is not allowlisted")


def main() -> None:
    os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"
    if os.geteuid() != 0: fail("This helper must be launched through pkexec")
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict): raise ValueError
    except (json.JSONDecodeError, ValueError):
        fail("Invalid request")
    try:
        data = perform(request)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        fail(str(error))
    print(json.dumps({"ok": True, "data": data}))


if __name__ == "__main__": main()
