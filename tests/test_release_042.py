from types import SimpleNamespace
import pytest
from nitrosense import keyboard, helper


@pytest.mark.parametrize("mode", range(1, 6))
def test_keyboard_effect_protocol(mode):
    payload = keyboard.dynamic_payload(mode, 4, 80, 1, [120, 80, 255])
    assert len(payload) == 16
    assert payload[:10] == bytes([mode, 4, 80, 8 if mode == 3 else 0, 1, 120, 80, 255, 0, 1])
    assert payload[10:] == bytes(6)


@pytest.mark.parametrize("args", [(8, 4, 80, 1, [0, 0, 0]), (3, 10, 80, 1, [0, 0, 0]),
    (3, 4, 101, 1, [0, 0, 0]), (3, 4, 80, 0, [0, 0, 0]), (3, 4, 80, 1, [256, 0, 0]),
    (True, 4, 80, 1, [0, 0, 0])])
def test_invalid_effect_is_rejected_before_device_write(args):
    with pytest.raises(ValueError):
        keyboard.dynamic_payload(*args)


def test_helper_dispatches_effect_without_static_zone_write(monkeypatch):
    calls = []
    monkeypatch.setattr(helper, "apply_effect", lambda *args: calls.append(args))
    monkeypatch.setattr(helper, "apply_static", lambda *args, **kw: pytest.fail("Static write during effect"))
    helper.perform({"action": "keyboard", "mode": 3, "speed": 5, "brightness": 75,
                    "direction": 2, "colour": [1, 2, 3]})
    assert calls == [(3, 5, 75, 2, [1, 2, 3])]


def test_rpm_change_refreshes_speed_gauge():
    from nitrosense.widgets import FanDial
    face = object()
    fake = SimpleNamespace(rpm=2000, temperature=50, face=face, queue_draw=lambda: None)
    FanDial.update(fake, 2100, 50)
    assert fake.face is None
    FanDial.update(fake, 2100, 51)
    assert fake.face is None


def test_gui_rendering_overrides_do_not_leak_into_game(monkeypatch):
    from nitrosense import runtime
    for key in ("GSK_RENDERER", "GDK_DISABLE", "GSK_CACHE_TIMEOUT", "DISABLE_MANGOHUD", "__EGL_VENDOR_LIBRARY_FILENAMES"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(runtime, "_changed", {})
    monkeypatch.setattr(runtime, "_configured", False)
    monkeypatch.setattr(runtime, "primary_mesa_vendor", lambda: "/system/mesa.json")
    before = dict(runtime.os.environ)
    runtime.configure()
    assert runtime.os.environ["DISABLE_MANGOHUD"] == "1"
    assert runtime.os.environ["GSK_RENDERER"] == "gl"
    assert runtime.child_environment() == before


def test_explicit_renderer_and_gpu_choice_are_preserved(monkeypatch):
    from nitrosense import runtime
    monkeypatch.setattr(runtime, "_changed", {})
    monkeypatch.setattr(runtime, "_configured", False)
    monkeypatch.setenv("GSK_RENDERER", "vulkan")
    monkeypatch.setenv("DRI_PRIME", "1")
    monkeypatch.setenv("DISABLE_MANGOHUD", "0")
    before = dict(runtime.os.environ)
    runtime.configure()
    assert runtime.os.environ["GSK_RENDERER"] == "vulkan"
    assert runtime.child_environment() == before


def test_fans_stay_active_when_settings_has_focus():
    from nitrosense.widgets import animation_active
    main = SimpleNamespace(is_active=lambda: False)
    settings = SimpleNamespace(is_active=lambda: True)
    application = SimpleNamespace(get_windows=lambda: [main, settings])
    main.get_application = lambda: application
    assert animation_active(main)
    settings.is_active = lambda: False
    assert not animation_active(main)


def test_nvml_session_closes_and_can_reconnect():
    from nitrosense.nvidia import Nvidia
    reader = Nvidia()
    calls = []
    reader.lib = SimpleNamespace(nvmlShutdown=lambda: calls.append("shutdown"))
    reader.retry_at = 123
    reader.static = ("old",)
    reader.disconnect()
    assert calls == ["shutdown"]
    assert reader.lib is None and reader.retry_at == 0 and reader.static is None
    reader.disconnect()
    assert calls == ["shutdown"]
