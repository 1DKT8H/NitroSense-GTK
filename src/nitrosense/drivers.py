"""Distribution adapters. Use distribution recommendations, never a downloaded .run."""
import platform
from pathlib import Path
import re
import shutil
import subprocess
from . import i18n


def distro():
    try:
        info = platform.freedesktop_os_release()
    except OSError:
        info = {}
    return info.get("ID", ""), info.get("ID_LIKE", "").split()


def distro_name():
    try:
        return platform.freedesktop_os_release().get("PRETTY_NAME", distro()[0] or "Linux")
    except OSError:
        return "Linux"


def driver_help():
    ident, likes = distro()
    if ident == "ubuntu" or "ubuntu" in likes:
        detail = "Dobór pakietu przez ubuntu-drivers do GPU i wersji systemu; nie przez najwyższy numer wersji NVIDIA."
    else:
        detail = "Pakiet musi pasować do GPU, kernela i repozytoriów tej dystrybucji. Automatyczna instalacja jest wyłączona bez zweryfikowanego adaptera; NitroSense nie uruchomi poleceń Ubuntu na tym systemie."
    return distro_name() + "\n" + i18n.tr(detail)


def nvidia_present():
    return any((path / "vendor").read_text().strip() == "0x10de" and
               (path / "class").read_text().strip().startswith("0x03")
               for path in Path("/sys/bus/pci/devices").glob("*")
               if (path / "vendor").exists() and (path / "class").exists())


def recommendation():
    ident, likes = distro()
    if not nvidia_present():
        return {"detail": "Sterowniki Intel/AMD są dostarczane przez kernel i Mesa w Twojej dystrybucji.",
                "supported": False}
    if (ident == "ubuntu" or "ubuntu" in likes) and shutil.which("ubuntu-drivers"):
        result = subprocess.run(["ubuntu-drivers", "devices"], capture_output=True, text=True, timeout=40)
        package = next((re.search(r"nvidia-driver-[\w.-]+", line).group()
                        for line in result.stdout.splitlines()
                        if "recommended" in line and re.search(r"nvidia-driver-[\w.-]+", line)), None)
        return {"detail": distro_name() + "\n" + i18n.tr("Zalecany pakiet") + ": " + (package or "—"),
                "supported": bool(package) and result.returncode == 0, "package": package, "kind": "ubuntu"}
    return {"detail": driver_help(), "supported": False}


def install_commands():
    ident, likes = distro()
    if (ident == "ubuntu" or "ubuntu" in likes) and shutil.which("ubuntu-drivers") and recommendation()["supported"]:
        return [["apt-get", "update"], ["ubuntu-drivers", "install"]]
    raise RuntimeError("Automatyczna instalacja sterownika nie jest obsługiwana na tej dystrybucji")


def overlay_install_commands():
    ident, likes = distro()
    if ident in ("ubuntu", "debian") or "debian" in likes:
        return [["apt-get", "install", "-y", "mangohud"]]
    if ident == "fedora":
        return [["dnf", "install", "-y", "mangohud"]]
    raise RuntimeError("Zainstaluj mangohud w menedżerze pakietów dystrybucji")
