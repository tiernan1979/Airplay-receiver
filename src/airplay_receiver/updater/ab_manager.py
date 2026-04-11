import os
import shutil
import tempfile

BASE = os.path.join(tempfile.gettempdir(), "airplay_app")


def paths():
    return {
        "base": BASE,
        "current": os.path.join(BASE, "current"),
        "next": os.path.join(BASE, "next"),
        "backup": os.path.join(BASE, "backup"),
        "flag": os.path.join(BASE, "update.flag"),
    }


def ensure_dirs():
    p = paths()
    for k in ["current", "next", "backup"]:
        os.makedirs(p[k], exist_ok=True)


def stage_update(file_path):
    p = paths()
    ensure_dirs()

    shutil.copy2(file_path, os.path.join(p["next"], "AirPlayReceiver.exe"))

    with open(p["flag"], "w") as f:
        f.write("pending")


def swap_versions():
    p = paths()

    if not os.path.exists(p["flag"]):
        return False

    try:
        # backup current
        if os.path.exists(p["backup"]):
            shutil.rmtree(p["backup"])

        if os.path.exists(p["current"]):
            shutil.copytree(p["current"], p["backup"])

        # move next → current
        if os.path.exists(p["current"]):
            shutil.rmtree(p["current"])

        shutil.move(p["next"], p["current"])

        os.remove(p["flag"])
        return True

    except Exception:
        return False


def rollback():
    p = paths()

    if not os.path.exists(p["backup"]):
        return False

    if os.path.exists(p["current"]):
        shutil.rmtree(p["current"])

    shutil.copytree(p["backup"], p["current"])
    return True


def get_executable():
    p = paths()
    return os.path.join(p["current"], "AirPlayReceiver.exe")