"""Rendering policy for this GUI only. Never leak it into games or launchers."""
import json
import os
from pathlib import Path

_changed = {}
_configured = False


def primary_mesa_vendor():
    """Use Mesa only when DRM reports an Intel primary display adapter."""
    try:
        primary = any((card / "device/vendor").read_text().strip() == "0x8086" and
                      (card / "device/boot_vga").read_text().strip() == "1"
                      for card in Path("/sys/class/drm").glob("card[0-9]*")
                      if card.name[4:].isdigit() and (card / "device").exists())
        if primary:
            for folder in ("/etc/glvnd/egl_vendor.d", "/usr/share/glvnd/egl_vendor.d"):
                for path in Path(folder).glob("*.json"):
                    if json.loads(path.read_text()).get("ICD", {}).get("library_path") == "libEGL_mesa.so.0":
                        return str(path)
    except (OSError, ValueError):
        pass
    return None


def configure():
    global _configured
    if _configured:
        return
    _configured = True
    def set_local(key, value, default=True):
        if not default or key not in os.environ:
            _changed[key] = os.environ.get(key)
            os.environ[key] = value
    set_local("DISABLE_MANGOHUD", "1", default=False)
    set_local("GSK_RENDERER", "gl")
    set_local("GSK_CACHE_TIMEOUT", "2")
    if os.environ.get("GSK_RENDERER") in ("gl", "ngl", "opengl"):
        disabled = set(os.environ.get("GDK_DISABLE", "").replace(",", " ").split())
        if "vulkan" not in disabled:
            set_local("GDK_DISABLE", ",".join(sorted(disabled | {"vulkan"})), default=False)
        # Explicit user offload requests always win.
        if not any(os.environ.get(key) for key in ("DRI_PRIME", "__NV_PRIME_RENDER_OFFLOAD", "__EGL_VENDOR_LIBRARY_FILENAMES")):
            vendor = primary_mesa_vendor()
            if vendor:
                set_local("__EGL_VENDOR_LIBRARY_FILENAMES", vendor)


def child_environment():
    env = dict(os.environ)
    for key, original in _changed.items():
        if original is None:
            env.pop(key, None)
        else:
            env[key] = original
    return env


def restore_launch_context(context):
    env = child_environment()
    for key in _changed:
        if key in env:
            context.setenv(key, env[key])
        else:
            context.unsetenv(key)
