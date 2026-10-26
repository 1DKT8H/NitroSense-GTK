"""MangoHud integration: renderer-level overlay on Vulkan/OpenGL, including Proton."""
import os
from pathlib import Path
import shlex
import socket
import sys
import json
import shutil
import subprocess
from dataclasses import dataclass
from . import settings
from .runtime import child_environment, restore_launch_context

FIELDS = {
    "fps": "FPS", "frametime": "Frametime", "frame_timing": "Wykres frametime",
    "cpu_stats": "Obciążenie CPU", "gpu_stats": "Obciążenie GPU",
    "cpu_temp": "Temperatura CPU", "gpu_temp": "Temperatura GPU",
    "cpu_power": "Moc CPU", "gpu_power": "Moc GPU",
    "cpu_mhz": "Zegar CPU", "gpu_core_clock": "Zegar GPU",
    "gpu_mem_clock": "Zegar VRAM", "gpu_power_limit": "Limit mocy GPU",
    "gpu_fan": "Wentylator GPU (jeśli dostępny)", "core_load": "Obciążenie rdzeni CPU",
    "gpu_name": "Model GPU", "vulkan_driver": "Sterownik Vulkan",
    "procmem": "Pamięć procesu", "swap": "Swap", "io_read": "Odczyt dysku gry",
    "io_write": "Zapis dysku gry", "battery": "Bateria", "battery_watt": "Moc baterii",
    "ram": "RAM", "vram": "VRAM",
    "throttling_status": "Ograniczenia GPU (temperatura / moc)",
    "throttling_status_graph": "Ograniczenia GPU na wykresie",
}
DEFAULT = ["fps", "frametime", "cpu_temp", "gpu_temp", "cpu_power", "gpu_power", "throttling_status"]


def configuration(selected=None):
    selected = DEFAULT if selected is None else selected
    lines = ["legacy_layout=0", "background_alpha=0.45", "font_size=18", "round_corners=8",
             "position=top-left", "toggle_hud=Shift_R+F12", "fps_sampling_period=500",
             f"control=nitrosense-{os.getuid()}-%p"]
    lines.extend(key + ("=1" if key in selected else "=0") for key in FIELDS)
    if "gpu_mem_clock" in selected and "vram" not in selected:
        lines.append("vram=1")
    return "# Managed by NitroSense\n" + "\n".join(lines) + "\n"


def save_config(selected):
    folder = settings.config_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "MangoHud.conf"
    target.write_text(configuration(selected))
    values = settings.read()
    values["overlay_fields"] = [key for key in selected if key in FIELDS]
    settings.save(values)
    global_config = global_config_path()
    if global_config.exists() and global_config.read_text().startswith("# Managed by NitroSense"):
        global_config.write_text(configuration(selected))
    return target


def global_config_path():
    return settings.config_dir().parent / "MangoHud" / "MangoHud.conf"


def layer_dir():
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "vulkan/implicit_layer.d"


def global_enabled():
    return any(layer_dir().glob("nitrosense-MangoHud*.json"))


def set_global(enabled):
    """User-local Vulkan activation. Never modifies the distro's layer files."""
    directory = layer_dir()
    if not enabled:
        for path in directory.glob("nitrosense-MangoHud*.json"):
            data = json.loads(path.read_text())
            if data.get("nitrosense_managed"):
                path.unlink()
        return
    sources = list(Path("/usr/share/vulkan/implicit_layer.d").glob("MangoHud*.json"))
    if not sources:
        raise RuntimeError("Nie znaleziono warstwy Vulkan MangoHud. Zainstaluj nakładkę.")
    target = global_config_path()
    if target.exists() and not target.read_text().startswith("# Managed by NitroSense"):
        raise RuntimeError("Masz własny MangoHud.conf. Zachowano go; użyj uruchamiania gry z NitroSense zamiast trybu automatycznego.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(configuration(settings.read().get("overlay_fields", DEFAULT)))
    directory.mkdir(parents=True, exist_ok=True)
    for source in sources:
        document = json.loads(source.read_text())
        document["layer"].pop("enable_environment", None)
        document["nitrosense_managed"] = True
        destination = directory / ("nitrosense-" + source.name)
        if destination.exists() and not json.loads(destination.read_text()).get("nitrosense_managed"):
            raise RuntimeError("Istniejący plik warstwy nie należy do NitroSense")
        destination.write_text(json.dumps(document, indent=2))


FLATPAK_APPS = {"com.heroicgameslauncher.hgl": "Heroic", "net.lutris.Lutris": "Lutris",
                "com.valvesoftware.Steam": "Steam", "com.usebottles.bottles": "Bottles"}


@dataclass(frozen=True)
class Integration:
    id: str
    name: str
    kind: str
    supported: bool
    detail: str
    runtime: str = ""


def desktop_apps():
    from gi.repository import Gio
    return Gio.AppInfo.get_all()


def integrations():
    result = []
    flatpak_games = set(FLATPAK_APPS)
    for app in desktop_apps():
        if not app.should_show() or not hasattr(app, "get_categories"):
            continue
        categories = (app.get_categories() or "").split(";")
        if "Game" not in categories:
            continue
        flatpak_id = app.get_string("X-Flatpak")
        if flatpak_id:
            flatpak_games.add(flatpak_id)
            continue
        command = app.get_executable() or ""
        sandbox = bool(app.get_string("X-SnapInstanceName")) or "/snap/" in command or command in ("snap", "flatpak")
        result.append(Integration(app.get_id(), app.get_display_name(), "Snap" if sandbox else "System",
            not sandbox, "Ten sandbox wymaga osobnej integracji." if sandbox else
            "Uruchomienie z MangoHud dla Vulkan. Zamknij działający launcher przed uruchomieniem; OpenGL może wymagać osobnej konfiguracji."))
    if shutil.which("flatpak"):
        installed = subprocess.run(["flatpak", "list", "--app", "--columns=application,name,runtime"],
                                   capture_output=True, text=True, timeout=10).stdout.splitlines()
        seen = set()
        for line in installed:
            parts = line.split("\t")
            if len(parts) != 3 or parts[0] not in flatpak_games or parts[0] in seen:
                continue
            app_id, name, runtime = parts
            seen.add(app_id)
            supported = runtime.startswith("org.freedesktop.Platform/") and len(runtime.split("/")) == 3
            result.append(Integration(app_id, name, "Flatpak", supported,
                "Konfiguracja dodatku MangoHud dla runtime tej aplikacji." if supported else
                "Ten runtime nie ma jeszcze zweryfikowanego adaptera MangoHud.", runtime))
    return sorted(result, key=lambda item: (item.name.casefold(), item.kind))


def launch_desktop(app_id):
    from gi.repository import Gio
    entry = next((item for item in integrations() if item.id == app_id and item.kind == "System" and item.supported), None)
    if entry is None:
        raise ValueError("Game or launcher is no longer available")
    if not shutil.which("mangohud"):
        raise RuntimeError("Nakładka nie jest zainstalowana")
    app = Gio.DesktopAppInfo.new(app_id)
    if not app:
        raise ValueError("Desktop entry is no longer available")
    config = save_config(settings.read().get("overlay_fields", DEFAULT))
    context = Gio.AppLaunchContext()
    restore_launch_context(context)
    context.setenv("DISABLE_MANGOHUD", "0")
    context.setenv("MANGOHUD", "1")
    context.setenv("MANGOHUD_CONFIGFILE", str(config))
    if not app.launch([], context):
        raise RuntimeError("Launcher could not be started")


def configure_flatpak(app_id, progress=lambda _message: None):
    if not any(item.id == app_id and item.kind == "Flatpak" and item.supported for item in integrations()):
        raise ValueError("Unsupported launcher")
    info = subprocess.run(["flatpak", "info", "--show-runtime", app_id], capture_output=True,
                          text=True, check=True, timeout=15).stdout.strip().split("/")
    if len(info) != 3 or info[0] != "org.freedesktop.Platform":
        raise RuntimeError("Ta wersja launchera wymaga osobnego doboru dodatku Flatpak")
    arch, branch = info[1:]
    if not all(part.replace(".", "").replace("_", "").isalnum() for part in (arch, branch)):
        raise ValueError("Invalid Flatpak runtime")
    extension = f"org.freedesktop.Platform.VulkanLayer.MangoHud/{arch}/{branch}"
    progress("Pobieranie dodatku MangoHud dla Flatpaka…")
    user_remotes = subprocess.run(["flatpak", "remotes", "--user", "--columns=name"],
                                 capture_output=True, text=True, timeout=10).stdout.splitlines()
    scope = "--user" if "flathub" in user_remotes else "--system"
    result = subprocess.run(["flatpak", "install", scope, "-y", "--noninteractive", "flathub", extension],
                            capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-2000:])
    config = save_config(settings.read().get("overlay_fields", DEFAULT))
    progress("Konfigurowanie nakładki dla launchera…")
    result = subprocess.run(["flatpak", "override", "--user", "--env=MANGOHUD=1",
                            "--env=MANGOHUD_CONFIGFILE=" + str(config),
                            "--filesystem=" + str(config.parent) + ":ro", app_id],
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr)
    values = settings.read()
    configured = values.get("flatpak_integrations", [])
    values["flatpak_integrations"] = sorted(set([*configured, app_id]))
    settings.save(values)


def launch_game(argv):
    if not argv:
        raise ValueError("Wybierz plik gry lub launchera")
    if not shutil.which("mangohud"):
        raise RuntimeError("Nakładka nie jest zainstalowana")
    config = save_config(settings.read().get("overlay_fields", DEFAULT))
    return subprocess.Popen(["mangohud", *argv], env=dict(child_environment(),
                            MANGOHUD="1", DISABLE_MANGOHUD="0", MANGOHUD_CONFIGFILE=str(config)),
                            start_new_session=True)


def steam_command():
    return "MANGOHUD_CONFIGFILE=" + shlex.quote(str(settings.config_dir() / "MangoHud.conf")) + " mangohud %command%"


def toggle():
    count = 0
    prefix = "@nitrosense-" + str(os.getuid()) + "-"
    try:
        lines = Path("/proc/net/unix").read_text().splitlines()
    except OSError:
        return 0
    for line in lines:
        fields = line.split()
        if len(fields) < 8 or not fields[7].startswith(prefix):
            continue
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(.2)
                client.connect("\0" + fields[7][1:])
                client.sendall(b":hud;")
                count += 1
        except OSError:
            continue
    return count


def launch(argv):
    if not argv:
        raise SystemExit("Usage: nitrosense-game GAME [ARGUMENTS]")
    config = settings.config_dir() / "MangoHud.conf"
    if not config.exists():
        save_config(DEFAULT)
    os.environ["MANGOHUD_CONFIGFILE"] = str(config)
    os.execvp("mangohud", ["mangohud", *argv])


def main():
    if "--toggle" in sys.argv:
        toggle()
    else:
        launch(sys.argv[1:])


if __name__ == "__main__":
    main()
