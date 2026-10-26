import ctypes
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest
from nitrosense import helper, routine, overlay, keyfilter, settings, hardware


@pytest.mark.parametrize("action", ["install_overlay", "install_rgb", "install_drivers", "undervolt",
                                   "gpu_offset", "cpu_power_limits", "cpu_power_window", "arbitrary"])
def test_passwordless_endpoint_rejects_privileged_operations(action):
    with pytest.raises(ValueError):
        routine.validate({"action": action})


def test_policy_only_grants_active_local_session():
    root = Path(__file__).parents[1]
    policy = ET.parse(root / "share/polkit-1/actions/io.github.nitrosense.routine.policy")
    defaults = policy.find("action/defaults")
    assert defaults.findtext("allow_active") == "yes"
    assert defaults.findtext("allow_inactive") == "no"
    assert defaults.findtext("allow_any") == "no"
    main_policy = ET.parse(root / "share/polkit-1/actions/io.github.nitrosense.NitroSense.policy")
    assert main_policy.findtext("action/defaults/allow_active") == "auth_admin"


@pytest.mark.parametrize("enabled,byte", [(True, 0x1e), (False, 0)])
def test_keyboard_timeout_uses_legacy_an51555_register(monkeypatch, enabled, byte):
    writes = []
    monkeypatch.setattr(helper, "detect_profile", lambda: hardware.AN515_55)
    monkeypatch.setattr(helper, "write_ec", lambda address, value: writes.append((address, value)))
    helper.perform({"action": "keyboard_timeout", "enabled": enabled})
    assert writes == [(0x06, byte)]


def test_key_filter_never_allows_typing_codes():
    mask = keyfilter.mask_for(keyfilter.APPLICATION_KEYS)
    allowed = [i for i in range(768) if mask[i // 8] & (1 << (i % 8))]
    assert allowed == sorted(keyfilter.APPLICATION_KEYS)
    assert not mask[30 // 8] & (1 << (30 % 8))  # A
    assert not mask[28 // 8] & (1 << (28 % 8))  # Enter


def test_kernel_filter_blocks_scancodes(monkeypatch):
    import struct
    records = {}
    def ioctl(fd, code, argument):
        kind, size, ptr = struct.unpack("=IIQ", argument)
        records[kind] = ctypes.string_at(ptr, size)
        assert code == keyfilter.EVIOCSMASK
    monkeypatch.setattr(keyfilter.fcntl, "ioctl", ioctl)
    keyfilter.restrict(123)
    assert records[1] == keyfilter.mask_for(keyfilter.APPLICATION_KEYS)
    assert records[4] == bytes(96)  # EV_MSC scancodes


def test_overlay_configuration_and_required_vram():
    value = overlay.configuration(["gpu_mem_clock", "gpu_power"])
    assert "gpu_power=1" in value and "cpu_power=0" in value
    assert value.rstrip().endswith("vram=1")
    assert "control=nitrosense-" in value


def test_config_does_not_overwrite_unmanaged_global_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = overlay.global_config_path()
    target.parent.mkdir()
    target.write_text("user_config=untouched\n")
    overlay.save_config(["fps"])
    assert target.read_text() == "user_config=untouched\n"


def test_global_disable_only_removes_managed_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folder = overlay.layer_dir()
    folder.mkdir(parents=True)
    managed = folder / "nitrosense-MangoHud.x86_64.json"
    other = folder / "nitrosense-MangoHud.custom.json"
    managed.write_text(json.dumps({"nitrosense_managed": True}))
    other.write_text(json.dumps({"user": True}))
    overlay.set_global(False)
    assert not managed.exists() and other.exists()


def test_launch_game_does_not_execute_shell_fragments(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(overlay.shutil, "which", lambda _: "/usr/bin/mangohud")
    calls = []
    monkeypatch.setattr(overlay.subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw)))
    overlay.launch_game(["/games/test; echo nope"])
    assert calls[0][0] == ["mangohud", "/games/test; echo nope"]
    assert "shell" not in calls[0][1]


def test_core_cache_offsets_are_independent(monkeypatch):
    from contextlib import nullcontext
    calls = []
    monkeypatch.setattr(helper, "detect_profile", lambda: hardware.AN515_55)
    monkeypatch.setattr(helper, "run_checked", calls.append)
    monkeypatch.setattr(helper, "voltage_lock", nullcontext)
    helper.perform({"action": "undervolt", "core_mv": -80, "cache_mv": -60})
    assert calls == [["undervolt", "--core", "-80", "--cache", "-60"]]


def test_profile_does_not_match_suffix_model(monkeypatch):
    monkeypatch.setattr(hardware, "dmi_product_name", lambda: "AN515-55-UNKNOWN")
    assert hardware.detect_profile() is None
