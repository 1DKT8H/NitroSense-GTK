"""Bounded OC-mailbox readback for the verified Comet Lake CPU family.

Opcode 0x10 selects a read; 0x11 (write offset) is never issued here.
Offsets are not physical Vcore measurements. Other families need an adapter.
"""
import os
import time
from pathlib import Path


def decode_offset(response):
    if response & (1 << 63) or (response >> 32) & 0xff:
        raise RuntimeError("OC mailbox rejected the voltage read")
    raw = (response >> 21) & 0x7ff
    return round((raw if raw < 1024 else raw - 2048) / 1.024, 2)


def read_offsets():
    from .hardware import detect_profile
    info = Path("/proc/cpuinfo").read_text()
    first = dict(line.split(":", 1) for line in info.split("\n\n")[0].splitlines() if ":" in line)
    fields = {key.strip(): value.strip() for key, value in first.items()}
    if (not detect_profile() or fields.get("vendor_id") != "GenuineIntel"
            or fields.get("cpu family") != "6" or fields.get("model") != "165"):
        raise RuntimeError("Voltage readback has no verified adapter for this CPU")
    result = {}
    fd = os.open("/dev/cpu/0/msr", os.O_RDWR | os.O_CLOEXEC)
    try:
        for name, plane in (("core_mv", 0), ("cache_mv", 2)):
            command = (1 << 63) | (plane << 40) | (0x10 << 32)
            if os.pwrite(fd, command.to_bytes(8, "little"), 0x150) != 8:
                raise OSError("Incomplete OC-mailbox request")
            for _ in range(10):
                data = os.pread(fd, 8, 0x150)
                if len(data) != 8:
                    raise OSError("Incomplete OC-mailbox response")
                response = int.from_bytes(data, "little")
                if not response & (1 << 63):
                    break
                time.sleep(.001)
            result[name] = decode_offset(response)
    finally:
        os.close(fd)
    return result
