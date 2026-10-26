"""Read-only hardware service. No write commands, paths or register arguments in IPC."""
from __future__ import annotations
import json
import os
from pathlib import Path
import selectors
import socket
import struct
import time

from .hardware import detect_profile
from .telemetry import Snapshot, _cpu_power, read_text
from .keyfilter import restrict, APPLICATION_KEYS

SOCKET = "/run/nitrosense/hardware.sock"
EVENT = struct.Struct("@llHHi")


def query() -> dict:
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.25)
            client.connect(SOCKET)
            data = bytearray()
            while len(data) < 32768:
                part = client.recv(4096)
                if not part:
                    break
                data.extend(part)
            return json.loads(data)
    except (OSError, ValueError):
        return {}


def sample() -> dict:
    values = {}
    profile = detect_profile()
    if profile:
        for path in ("/sys/kernel/debug/ec/ec0/io", "/dev/ec"):
            try:
                with open(path, "rb", buffering=0) as ec:
                    def reg(address):
                        ec.seek(address)
                        data = ec.read(1)
                        if len(data) != 1:
                            raise OSError("Short EC read")
                        return data[0]
                    for key in ("cpu", "gpu"):
                        # 0x13/0x15 are the low bytes, despite the legacy labels.
                        low = reg(getattr(profile, key + "_fan_hi"))
                        high = reg(getattr(profile, key + "_fan_lo"))
                        rpm = (high << 8) | low
                        values[key + "_fan"] = rpm if rpm <= 15000 else None
                        values[key + "_fan_mode"] = reg(getattr(profile, key + "_fan_mode"))
                        speed = reg(getattr(profile, key + "_fan_speed"))
                        values[key + "_fan_target"] = speed if 30 <= speed <= 100 else None
                    values["coolboost"] = reg(profile.coolboost) == 1
                    values["charge_limit"] = reg(profile.charge_limit) == 0x71
                    if profile.keyboard_timeout is not None:
                        values["keyboard_timeout"] = reg(profile.keyboard_timeout) == 0x1e
                    values["ec_available"] = True
                break
            except OSError:
                continue
    snap = Snapshot()
    _cpu_power(snap)
    values["cpu_power"] = snap.cpu_power
    rapl = Path("/sys/class/powercap/intel-rapl:0")
    for index, key in ((0, "pl1"), (1, "pl2")):
        raw = read_text(str(rapl / f"constraint_{index}_power_limit_uw"))
        if raw.isdigit():
            values[key] = int(raw) / 1e6
    window = read_text(str(rapl / "constraint_0_time_window_us"))
    if window.isdigit():
        values["pl1_window"] = int(window) / 1e6
    # Architectural thermal status: bit 0 = thermal throttling active now.
    try:
        with open("/dev/cpu/0/msr", "rb", buffering=0) as msr:
            def read_register(address):
                msr.seek(address)
                return int.from_bytes(msr.read(8), "little")
            if profile:  # MSR layout validated only for the AN515-55 Intel profile.
                status = read_register(0x1B1)
                values["cpu_throttled"] = bool(status & 1)
                target = read_register(0x1A2)
                values["cpu_critical"] = (target >> 16) & 0xff
    except OSError:
        pass
    return values


def serve() -> None:
    if os.geteuid() != 0:
        raise SystemExit("The hardware service requires root")
    folder = Path(SOCKET).parent
    folder.mkdir(mode=0o755, exist_ok=True)
    path = Path(SOCKET)
    if path.exists():
        path.unlink()
    selector = selectors.DefaultSelector()
    server = socket.socket(socket.AF_UNIX)
    server.bind(SOCKET)
    os.chmod(SOCKET, 0o666)  # Exposes only the allowlisted read-only sample.
    server.listen(8)
    selector.register(server, selectors.EVENT_READ, "client")
    key_sequence = 0
    key_code = None
    inputs = set()
    cache, last_sample, last_scan = {}, 0, 0
    while True:
        now = time.monotonic()
        if now - last_scan > 10:
            last_scan = now
            for event in Path("/sys/class/input").glob("event*"):
                name = read_text(str(event / "device/name"))
                supported = name == "Acer WMI hotkeys" or (detect_profile() and name == "AT Translated Set 2 keyboard")
                if not supported or event.name in inputs:
                    continue
                fd = None
                try:
                    fd = os.open("/dev/input/" + event.name, os.O_RDONLY | os.O_NONBLOCK)
                    restrict(fd)  # Fail closed if event filtering is unsupported.
                    selector.register(fd, selectors.EVENT_READ, event.name)
                    inputs.add(event.name)
                except OSError:
                    if fd is not None:
                        os.close(fd)
        for ready, _ in selector.select(timeout=1):
            if ready.data == "client":
                client, _ = server.accept()
                try:
                    client.settimeout(.1)
                    now = time.monotonic()
                    if now - last_sample >= .4:
                        cache = sample()
                        last_sample = now
                    response = dict(cache, key_sequence=key_sequence, key_code=key_code,
                                    hotkey_available=bool(inputs))
                    client.sendall(json.dumps(response).encode())
                except OSError:
                    pass
                finally:
                    client.close()
            else:
                try:
                    data = os.read(ready.fd, EVENT.size * 32)
                    for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                        _, _, kind, code, value = EVENT.unpack_from(data, offset)
                        # Only special application keys from Acer WMI, never text input.
                        if kind == 1 and value == 1 and code in APPLICATION_KEYS:
                            key_sequence += 1
                            key_code = code
                except OSError:
                    selector.unregister(ready.fd)
                    os.close(ready.fd)
                    inputs.discard(ready.data)


if __name__ == "__main__":
    serve()
