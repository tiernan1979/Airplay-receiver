import requests
import tempfile
import os
import hashlib
import threading

from .ab_manager import stage_update

GITHUB_API = "https://api.github.com/repos/tiernan1979/Airplay-receiver/releases/latest"


# ─────────────────────────────────────────────
# CORE UPDATE CHECK
# ─────────────────────────────────────────────
def check_for_update():
    r = requests.get(GITHUB_API, timeout=10)
    data = r.json()

    latest_version = data["tag_name"]
    asset = data["assets"][0]

    return {
        "version": latest_version,
        "url": asset["browser_download_url"],
        "sha_url": asset["browser_download_url"] + ".sha256",
    }


# ─────────────────────────────────────────────
# DOWNLOAD FILE
# ─────────────────────────────────────────────
def download_file(url):
    path = os.path.join(tempfile.gettempdir(), "airplay_update.bin")

    with requests.get(url, stream=True, timeout=15) as r:
        r.raise_for_status()

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

    return path


# ─────────────────────────────────────────────
# SHA256 VERIFY
# ─────────────────────────────────────────────
def verify_sha256(file_path, expected_hash):
    h = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest().strip().lower() == expected_hash.strip().lower()


def fetch_sha(url):
    r = requests.get(url, timeout=10)
    return r.text.split()[0].strip()


# ─────────────────────────────────────────────
# MAIN UPDATE PIPELINE
# ─────────────────────────────────────────────
def run_update_check():
    try:
        update = check_for_update()

        installer_path = download_file(update["url"])
        expected_sha = fetch_sha(update["sha_url"])

        if not verify_sha256(installer_path, expected_sha):
            raise Exception("SHA256 verification failed")

        # IMPORTANT: stage only (A/B system handles install safely)
        stage_update(installer_path)

        return True, update["version"]

    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────
# BACKGROUND LOOP (SIMPLE)
# ─────────────────────────────────────────────
def start_background_updater(interval_seconds=86400, callback=None):
    def loop():
        while True:
            success, result = run_update_check()

            if success and callback:
                callback(result)  # notify UI

            import time
            time.sleep(interval_seconds)

    t = threading.Thread(target=loop, daemon=True)
    t.start()