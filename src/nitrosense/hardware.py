"""Hardware profiles. Add a fork's laptop here, never scatter EC constants in UI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EcProfile:
    name: str
    dmi_names: tuple[str, ...]
    cpu_fan_mode: int
    gpu_fan_mode: int
    cpu_fan_speed: int
    gpu_fan_speed: int
    coolboost: int
    charge_limit: int
    cpu_temp: int
    gpu_temp: int
    cpu_fan_hi: int
    cpu_fan_lo: int
    gpu_fan_hi: int
    gpu_fan_lo: int
    keyboard_timeout: int | None = None


# Validated against the original project's AN515-55 profile. Values which have not
# been independently validated are intentionally absent: forks add them explicitly.
AN515_55 = EcProfile(
    name="Acer Nitro 5 AN515-55",
    dmi_names=("Nitro AN515-55", "AN515-55"),
    cpu_fan_mode=0x22, gpu_fan_mode=0x21, cpu_fan_speed=0x37, gpu_fan_speed=0x3A,
    coolboost=0x10, charge_limit=0x03,
    cpu_temp=0xB0, gpu_temp=0xB6,
    cpu_fan_hi=0x13, cpu_fan_lo=0x14, gpu_fan_hi=0x15, gpu_fan_lo=0x16,
    keyboard_timeout=0x06,
)
PROFILES = (AN515_55,)


def dmi_product_name() -> str:
    try:
        return Path("/sys/class/dmi/id/product_name").read_text().strip()
    except OSError:
        return "Unknown device"


def detect_profile() -> EcProfile | None:
    name = dmi_product_name().lower()
    return next((p for p in PROFILES if any(x.lower() == name for x in p.dmi_names)), None)
