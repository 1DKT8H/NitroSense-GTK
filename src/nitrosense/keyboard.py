"""Protocol for the locally-installed acer-gkbbl driver; no network module required."""
from __future__ import annotations
from pathlib import Path

DYNAMIC = Path("/dev/acer-gkbbl-0")
STATIC = Path("/dev/acer-gkbbl-static-0")
MODES = ("Static", "Breath", "Neon", "Wave", "Shifting", "Zoom")


def dynamic_payload(mode, speed, brightness, direction, colour):
    if type(mode) is not int or mode not in range(1, 6):
        raise ValueError("Unknown keyboard effect")
    if type(speed) is not int or not 1 <= speed <= 9:
        raise ValueError("Effect speed must be between 1 and 9")
    if type(brightness) is not int or not 0 <= brightness <= 100:
        raise ValueError("Brightness must be between 0 and 100")
    if type(direction) is not int or direction not in (1, 2):
        raise ValueError("Invalid effect direction")
    if len(colour) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in colour):
        raise ValueError("Invalid RGB colour")
    return bytes([mode, speed, brightness, 8 if mode == 3 else 0, direction, *colour, 0, 1] + [0] * 6)


def apply_effect(mode, speed, brightness, direction, colour):
    payload = dynamic_payload(mode, speed, brightness, direction, colour)
    device = Path("/dev/nitrosense-rgb") if Path("/dev/nitrosense-rgb").exists() else DYNAMIC
    if not device.exists():
        raise RuntimeError("Keyboard effect interface is unavailable")
    device.write_bytes(payload)


def available() -> bool:
    return (Path("/dev/nitrosense-rgb").exists() and Path("/dev/nitrosense-rgb-static").exists()) or (DYNAMIC.exists() and STATIC.exists())


def apply_static(zone: int, red: int, green: int, blue: int, brightness: int = 100) -> None:
    if not available():
        raise RuntimeError("Keyboard driver unavailable: install/load acer-gkbbl")
    if not 0 <= zone <= 4 or not 0 <= brightness <= 100 or any(not 0 <= c <= 255 for c in (red, green, blue)):
        raise ValueError("Invalid keyboard colour or zone")
    zones = range(1, 5) if zone == 0 else (zone,)
    static = Path("/dev/nitrosense-rgb-static") if Path("/dev/nitrosense-rgb-static").exists() else STATIC
    dynamic = Path("/dev/nitrosense-rgb") if Path("/dev/nitrosense-rgb").exists() else DYNAMIC
    for current in zones:
        static.write_bytes(bytes((1 << (current - 1), red, green, blue)))
    dynamic.write_bytes(bytes([0, 0, brightness, 0, 0, 0, 0, 0, 0, 1] + [0] * 6))
