import json
import os
from pathlib import Path
import tempfile


def config_dir():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "nitrosense"


def read():
    try:
        value = json.loads((config_dir() / "settings.json").read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(values):
    folder = config_dir()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".settings-", dir=folder)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(values, stream, indent=2)
        os.replace(name, folder / "settings.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)
