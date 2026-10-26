"""Local-session routine controls and bounded readback; no tuning writes/installers."""
import json
import os
import sys
from .helper import perform, fail

ALLOWED = frozenset({"fan", "coolboost", "charge_limit", "keyboard", "keyboard_timeout", "read_uv"})


def validate(request):
    if not isinstance(request, dict) or request.get("action") not in ALLOWED:
        raise ValueError("Ta operacja wymaga autoryzacji administratora")
    return request


def main():
    os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"
    if os.geteuid() != 0:
        fail("Uruchom przez pkexec")
    try:
        request = validate(json.loads(sys.stdin.read(4097)))
        # Serialize the small EC transactions from UI and the Nitro key listener.
        import fcntl
        with open("/run/nitrosense-routine.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = perform(request)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        fail(str(error))
    print(json.dumps({"ok": True, "data": data}))


if __name__ == "__main__":
    main()
