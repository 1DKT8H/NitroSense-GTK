"""Read-only telemetry. Failures yield None; a missing tool never crashes the UI."""
from __future__ import annotations

import csv
import math
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .hardware import EcProfile


@dataclass(slots=True)
class Snapshot:
    cpu_usage: float | None = None
    gpu_usage: float | None = None
    cpu_clock: int | None = None
    cpu_temp: float | None = None
    gpu_temp: float | None = None
    cpu_power: float | None = None
    gpu_power: float | None = None
    gpu_clock: int | None = None
    vram_used: int | None = None
    vram_total: int | None = None
    cpu_fan: int | None = None
    gpu_fan: int | None = None
    battery: int | None = None
    charging: bool | None = None
    gpu_name: str | None = None
    gpu_limit: int | None = None
    ram_used: float | None = None
    ram_total: float | None = None
    gpu_driver: str | None = None
    gpu_vbios: str | None = None
    gpu_error: str | None = None
    cpu_critical: float | None = None
    gpu_critical: float | None = None
    cpu_throttled: bool | None = None
    gpu_throttled: bool | None = None
    gpu_power_limited: bool | None = None
    battery_health: float | None = None
    battery_cycles: int | None = None
    battery_power: float | None = None
    battery_full_wh: float | None = None
    battery_design_wh: float | None = None
    battery_status: str | None = None
    battery_voltage: float | None = None
    battery_model: str | None = None
    cpu_fan_mode: int | None = None
    gpu_fan_mode: int | None = None
    cpu_fan_target: int | None = None
    gpu_fan_target: int | None = None
    ec_available: bool = False
    coolboost: bool | None = None
    charge_limit: bool | None = None
    pl1: float | None = None
    pl2: float | None = None
    pl1_window: float | None = None
    keyboard_timeout: bool | None = None
    gpu_memory_clock: int | None = None
    gpu_pstate: int | None = None
    cpu_clocks: tuple = ()
    cpu_governor: str | None = None
    cpu_epp: str | None = None
    cpu_voltage: float | None = None
    cpu_turbo: bool | None = None
    cpu_max_perf: float | None = None


_last_cpu: tuple[int, int] | None = None
_last_energy: tuple[float, float] | None = None


def read_text(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def inventory() -> dict[str, str]:
    cpu = next((line.split(":", 1)[1].strip() for line in read_text("/proc/cpuinfo").splitlines()
                if line.startswith("model name")), "Procesor")
    gpu_name = "NVIDIA • oczekiwanie na odczyt"
    for path in Path("/proc/driver/nvidia/gpus").glob("*/information"):
        for line in read_text(str(path)).splitlines():
            if line.startswith("Model:"):
                gpu_name = line.split(":", 1)[1].strip()
    return {
        "cpu_name": cpu, "gpu_name": gpu_name,
        "cpu_driver": read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver") or "—",
        "gpu_driver": read_text("/sys/module/nvidia/version") or "Niedostępny",
        "kernel": platform.release(), "session": os.environ.get("XDG_SESSION_TYPE", "Nieznana"),
        "microcode": next((line.split(":", 1)[1].strip() for line in read_text("/proc/cpuinfo").splitlines()
                           if line.startswith("microcode")), "—"),
    }


def _cmd(args: list[str], timeout: float = 1.5) -> str:
    if not shutil.which(args[0]):
        return ""
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _number(path: Path, scale: float = 1.0) -> float | None:
    try:
        return float(path.read_text().strip()) / scale
    except (OSError, ValueError):
        return None


def _hwmon() -> tuple[float | None, float | None]:
    cpu = None
    for path in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
        value = _number(path, 1000)
        label = path.with_name(path.name.replace("_input", "_label"))
        try:
            text = label.read_text().lower()
        except OSError:
            text = ""
        if value is not None and ("package" in text or "tctl" in text):
            cpu = value
            break
    return cpu, None


def _system(snapshot: Snapshot) -> None:
    """Read /proc directly: no resident monitoring agent or extra dependency."""
    global _last_cpu
    try:
        parts = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        values = [int(item) for item in parts]
        # guest / guest_nice are already counted in user / nice.
        total, idle = sum(values[:8]), values[3] + (values[4] if len(values) > 4 else 0)
        if _last_cpu:
            total_delta, idle_delta = total - _last_cpu[0], idle - _last_cpu[1]
            if total_delta: snapshot.cpu_usage = round(100 * (1 - idle_delta / total_delta), 1)
        _last_cpu = (total, idle)
    except (OSError, ValueError, IndexError):
        pass
    try:
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
        total = int(info["MemTotal"].split()[0]) / 1024 / 1024
        available = int(info["MemAvailable"].split()[0]) / 1024 / 1024
        snapshot.ram_total, snapshot.ram_used = total, total - available
    except (OSError, ValueError, KeyError):
        pass
    try:
        values = [float(value.split()[3]) for value in Path("/proc/cpuinfo").read_text().splitlines() if value.startswith("cpu MHz")]
        snapshot.cpu_clock = round(sum(values) / len(values)) if values else None
        snapshot.cpu_clocks = tuple(round(value) for value in values)
    except (OSError, ValueError, IndexError):
        pass
    base = "/sys/devices/system/cpu/"
    snapshot.cpu_governor = read_text(base + "cpufreq/policy0/scaling_governor") or None
    snapshot.cpu_epp = read_text(base + "cpufreq/policy0/energy_performance_preference") or None
    turbo = read_text(base + "intel_pstate/no_turbo")
    snapshot.cpu_turbo = turbo == "0" if turbo in ("0", "1") else None
    snapshot.cpu_max_perf = _number(Path(base + "intel_pstate/max_perf_pct"))
    for label in Path("/sys/class/hwmon").glob("hwmon*/in*_label"):
        if read_text(str(label)).lower() in ("vcore", "cpu core"):
            snapshot.cpu_voltage = _number(label.with_name(label.name.replace("_label", "_input")), 1000)
            break


def _nvidia(snapshot: Snapshot) -> None:
    query = "name,temperature.gpu,power.draw,clocks.gr,utilization.gpu,memory.used,memory.total,power.limit,driver_version,vbios_version"
    if not shutil.which("nvidia-smi"):
        snapshot.gpu_error = "Brak nvidia-smi • sprawdź instalację sterownika NVIDIA"
        return
    try:
        result = subprocess.run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=1.5)
        if result.returncode or not result.stdout.strip():
            snapshot.gpu_error = "NVIDIA nie zwraca danych • szczegóły w diagnostyce sterownika"
            return
        parse_nvidia(result.stdout, snapshot)
    except (OSError, subprocess.SubprocessError):
        snapshot.gpu_error = "Przekroczono czas odczytu NVIDIA lub narzędzie jest niedostępne"


def parse_nvidia(raw: str, snapshot: Snapshot) -> None:
    """N/A in power must not erase clocks, driver or VRAM on mobile NVIDIA."""
    try:
        row = next(csv.reader(raw.strip().splitlines()))
    except (StopIteration, csv.Error):
        snapshot.gpu_error = "Niepoprawna odpowiedź NVIDIA"
        return
    if len(row) != 10:
        snapshot.gpu_error = "Niepełna odpowiedź NVIDIA"
        return
    snapshot.gpu_name, snapshot.gpu_driver, snapshot.gpu_vbios = row[0].strip(), row[8].strip(), row[9].strip()
    for index, key, convert in ((1, "gpu_temp", float), (2, "gpu_power", float), (3, "gpu_clock", int),
                                (4, "gpu_usage", float), (5, "vram_used", int),
                                (6, "vram_total", int), (7, "gpu_limit", float)):
        try:
            value = float(row[index])
            if math.isfinite(value):
                setattr(snapshot, key, convert(value))
        except (ValueError, OverflowError):
            continue


def _cpu_power(snapshot: Snapshot) -> None:
    global _last_energy
    for path in Path("/sys/class/powercap").glob("intel-rapl:*/energy_uj"):
        if read_text(str(path.parent / "name")) != "package-0":
            continue
        energy = _number(path)
        now = time.monotonic()
        if energy is None:
            return
        if _last_energy:
            delta, elapsed = energy - _last_energy[0], now - _last_energy[1]
            if delta < 0:
                delta += _number(path.parent / "max_energy_range_uj") or 0
            if delta >= 0 and 0 < elapsed < 10:
                snapshot.cpu_power = delta / elapsed / 1_000_000
        _last_energy = (energy, now)
        return


def _hwmon_fans(snapshot: Snapshot) -> None:
    for path in Path("/sys/class/hwmon").glob("hwmon*/fan*_input"):
        label = read_text(str(path.with_name(path.name.replace("_input", "_label")))).lower()
        rpm = _number(path)
        if rpm is None:
            continue
        if "cpu" in label:
            snapshot.cpu_fan = int(rpm)
        elif "gpu" in label:
            snapshot.gpu_fan = int(rpm)


def _battery(snapshot: Snapshot) -> None:
    batteries = list(Path("/sys/class/power_supply").glob("BAT*"))
    if not batteries:
        return
    base = batteries[0]
    try:
        snapshot.battery = int(base.joinpath("capacity").read_text())
        snapshot.battery_status = base.joinpath("status").read_text().strip()
        snapshot.charging = snapshot.battery_status == "Charging"
    except (OSError, ValueError):
        pass
    full = _number(base / "energy_full")
    design = _number(base / "energy_full_design")
    voltage = _number(base / "voltage_min_design") or _number(base / "voltage_now")
    if full is None or design is None:
        full = _number(base / "charge_full")
        design = _number(base / "charge_full_design")
        if full is not None and design and voltage:
            snapshot.battery_full_wh = full * voltage / 1e12
            snapshot.battery_design_wh = design * voltage / 1e12
    else:
        snapshot.battery_full_wh, snapshot.battery_design_wh = full / 1e6, design / 1e6
    if full is not None and design:
        snapshot.battery_health = 100 * full / design
    cycles = _number(base / "cycle_count")
    snapshot.battery_cycles = int(cycles) if cycles is not None else None
    snapshot.battery_voltage = _number(base / "voltage_now", 1e6)
    snapshot.battery_power = _number(base / "power_now", 1e6)
    if snapshot.battery_power is None:
        current = _number(base / "current_now", 1e6)
        if current is not None and snapshot.battery_voltage is not None:
            snapshot.battery_power = abs(current * snapshot.battery_voltage)
    snapshot.battery_model = read_text(str(base / "model_name"))


def _ec_fans(profile: EcProfile | None, snapshot: Snapshot) -> None:
    if not profile:
        return
    for filename in ("/sys/kernel/debug/ec/ec0/io", "/dev/ec"):
        try:
            with open(filename, "rb", buffering=0) as ec:
                buf = ec.read(256)
            if len(buf) < 256:
                continue
            if snapshot.cpu_temp is None:
                snapshot.cpu_temp = buf[profile.cpu_temp]
            if snapshot.gpu_temp is None:
                snapshot.gpu_temp = buf[profile.gpu_temp]
            # Legacy map names are reversed: 0x13/0x15 contain the low byte.
            snapshot.cpu_fan = (buf[profile.cpu_fan_lo] << 8) | buf[profile.cpu_fan_hi]
            snapshot.gpu_fan = (buf[profile.gpu_fan_lo] << 8) | buf[profile.gpu_fan_hi]
            return
        except OSError:
            continue


def read_snapshot(profile: EcProfile | None) -> Snapshot:
    result = Snapshot()
    result.cpu_temp, _ = _hwmon()
    _system(result)
    _cpu_power(result)
    from .nvidia import reader
    reader.sample(result)
    _battery(result)
    _hwmon_fans(result)
    _ec_fans(profile, result)
    from .broker import query
    extra = query()
    for key in ("cpu_power", "cpu_fan", "gpu_fan", "cpu_fan_mode", "gpu_fan_mode", "cpu_fan_target", "gpu_fan_target",
                "coolboost", "charge_limit", "keyboard_timeout", "ec_available", "cpu_critical", "cpu_throttled", "pl1", "pl2", "pl1_window"):
        if extra.get(key) is not None:
            setattr(result, key, extra[key])
    if result.cpu_critical is None:
        for path in Path("/sys/class/hwmon").glob("hwmon*/temp*_crit"):
            if "coretemp" == read_text(str(path.parent / "name")):
                result.cpu_critical = _number(path, 1000)
                break
    return result


def power_profile() -> str:
    return _cmd(["powerprofilesctl", "get"]) or "unavailable"
