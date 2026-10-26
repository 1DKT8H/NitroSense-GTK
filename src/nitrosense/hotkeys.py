"""Small optional listener for Acer's application key. No GTK and no keyboard grab."""
import json
import subprocess
import time
from .broker import query
from . import settings, overlay

ACTIONS = {
    "window": "Pokaż NitroSense",
    "overlay": "Pokaż / ukryj nakładkę w grze",
    "diagnostics": "Otwórz diagnostykę",
    "tuning": "Otwórz tuning",
    "fans_auto": "Wentylatory: Auto",
    "fans_max": "Wentylatory: maksimum",
}


def dispatch():
    action = settings.read().get("hotkey_action", "window")
    if action == "overlay":
        overlay.toggle()
    elif action in ("fans_auto", "fans_max"):
        mode = "auto" if action == "fans_auto" else "max"
        # Firmware writes still go through the same authenticated helper.
        for target in ("cpu", "gpu"):
            result = subprocess.run(["pkexec", "/usr/bin/nitrosense-routine"],
                input=json.dumps({"action": "fan", "target": target, "mode": mode}),
                text=True, capture_output=True, timeout=120)
            if result.returncode:
                break
    else:
        command = ["/usr/bin/nitrosense"]
        if action in ("diagnostics", "tuning"):
            command.append("--" + action)
        subprocess.Popen(command)


def main():
    previous = None
    while True:
        data = query()
        sequence = data.get("key_sequence")
        if sequence is not None:
            if previous is not None and sequence != previous:
                config = settings.read()
                if config.get("hotkey_code") is None or data.get("key_code") == config.get("hotkey_code"):
                    try:
                        dispatch()
                    except (OSError, subprocess.SubprocessError):
                        pass
            previous = sequence
        else:
            previous = None
        time.sleep(.5)


if __name__ == "__main__":
    main()
