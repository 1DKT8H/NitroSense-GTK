from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from nitrosense import drivers, overlay, voltage, hardware, helper


@pytest.mark.parametrize("ident,likes", [("arch", []), ("cachyos", ["arch"]), ("fedora", []), ("debian", [])])
def test_foreign_ubuntu_command_never_enables_driver_install(monkeypatch, ident, likes):
    monkeypatch.setattr(drivers, "distro", lambda: (ident, likes))
    monkeypatch.setattr(drivers, "distro_name", lambda: ident)
    monkeypatch.setattr(drivers, "nvidia_present", lambda: True)
    monkeypatch.setattr(drivers.shutil, "which", lambda _: "/usr/bin/ubuntu-drivers")
    monkeypatch.setattr(drivers.subprocess, "run", lambda *a, **kw: pytest.fail("Wrong distro command"))
    assert not drivers.recommendation()["supported"]
    assert drivers.driver_help().startswith(ident)
    with pytest.raises(RuntimeError):
        drivers.install_commands()


def test_ubuntu_requires_actual_recommendation(monkeypatch):
    monkeypatch.setattr(drivers, "distro", lambda: ("ubuntu", []))
    monkeypatch.setattr(drivers, "nvidia_present", lambda: True)
    monkeypatch.setattr(drivers.shutil, "which", lambda _: "/usr/bin/ubuntu-drivers")
    monkeypatch.setattr(drivers.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="no recommendation", returncode=0))
    assert not drivers.recommendation()["supported"]
    with pytest.raises(RuntimeError):
        drivers.install_commands()


@pytest.mark.parametrize("raw,expected", [(0, 0), (0xf3400000, -99.61), (0x40000000000, 0)])
def test_voltage_decoding(raw, expected):
    assert voltage.decode_offset(raw) == expected


@pytest.mark.parametrize("raw", [1 << 63, 1 << 32, 0x10 << 32])
def test_voltage_rejects_busy_or_error_completion(raw):
    with pytest.raises(RuntimeError):
        voltage.decode_offset(raw)


def test_mailbox_reads_only_fixed_planes_with_read_opcode(monkeypatch):
    monkeypatch.setattr(hardware, "detect_profile", lambda: hardware.AN515_55)
    monkeypatch.setattr(voltage.Path, "read_text", lambda _: "vendor_id : GenuineIntel\ncpu family : 6\nmodel : 165\n")
    writes = []
    monkeypatch.setattr(voltage.os, "open", lambda *a: 123)
    monkeypatch.setattr(voltage.os, "close", lambda *a: None)
    monkeypatch.setattr(voltage.os, "pwrite", lambda fd, data, addr: writes.append((int.from_bytes(data, "little"), addr)) or 8)
    monkeypatch.setattr(voltage.os, "pread", lambda *a: bytes(8))
    assert voltage.read_offsets() == {"core_mv": 0, "cache_mv": 0}
    assert writes == [(0x8000001000000000, 0x150), (0x8000021000000000, 0x150)]


def test_unknown_cpu_never_opens_msr(monkeypatch):
    monkeypatch.setattr(hardware, "detect_profile", lambda: hardware.AN515_55)
    monkeypatch.setattr(voltage.Path, "read_text", lambda _: "vendor_id : GenuineIntel\ncpu family : 6\nmodel : 999\n")
    monkeypatch.setattr(voltage.os, "open", lambda *a: pytest.fail("MSR accessed on unknown CPU"))
    with pytest.raises(RuntimeError):
        voltage.read_offsets()


class Desktop:
    def __init__(self, ident, name, flatpak=None, snap=False):
        self.ident, self.name, self.flatpak, self.snap = ident, name, flatpak, snap
    def should_show(self): return True
    def get_categories(self): return "Game;"
    def get_id(self): return self.ident
    def get_display_name(self): return self.name
    def get_executable(self): return "/snap/game" if self.snap else "/usr/bin/game"
    def get_string(self, key): return self.flatpak if key == "X-Flatpak" else None


def test_launcher_discovery_is_not_heroic_specific(monkeypatch):
    monkeypatch.setattr(overlay, "desktop_apps", lambda: [Desktop("custom.desktop", "My Game"),
        Desktop("prism.desktop", "Prism", "org.prismlauncher.PrismLauncher"), Desktop("snap.desktop", "Snap game", snap=True)])
    monkeypatch.setattr(overlay.shutil, "which", lambda _: "/usr/bin/flatpak")
    monkeypatch.setattr(overlay.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=
        "org.prismlauncher.PrismLauncher\tPrism\torg.kde.Platform/x86_64/6.10\n"
        "com.valvesoftware.Steam\tSteam\torg.freedesktop.Platform/x86_64/25.08\n"))
    found = {item.name: item for item in overlay.integrations()}
    assert found["My Game"].kind == "System" and found["My Game"].supported
    assert found["Steam"].supported
    assert not found["Prism"].supported
    assert not found["Snap game"].supported
    assert "Heroic" not in found


def test_fan_requests_coalesce_and_wait_while_busy(monkeypatch):
    from nitrosense.app import NitroApplication, GLib
    removed, requests = [], []
    monkeypatch.setattr(GLib, "timeout_add", lambda *a: 42)
    monkeypatch.setattr(GLib, "source_remove", removed.append)
    fake = SimpleNamespace(pending_fans={}, fan_timer=0, alive=True, ec_available=True, busy=True,
                           flush_fans=lambda: None, _privileged=requests.append)
    NitroApplication.queue_fan(fake, "cpu", 2, 40)
    NitroApplication.queue_fan(fake, "cpu", 2, 80)
    assert len(fake.pending_fans) == 1 and removed == [42]
    assert NitroApplication.flush_fans(fake) is True and not requests
    fake.busy = False
    NitroApplication.flush_fans(fake)
    assert requests == [{"action": "fan", "target": "cpu", "mode": "manual", "speed": 80}]
    assert NitroApplication.flush_fans(fake) is False
