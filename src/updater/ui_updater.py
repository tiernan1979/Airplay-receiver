import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import os
import sys
import subprocess
import shutil
import time
import hashlib

GITHUB_API = "https://api.github.com/repos/tiernan1979/Airplay-receiver/releases/latest"


class UpdaterUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AirPlay Receiver Updater")
        self.root.geometry("420x180")
        self.root.resizable(False, False)

        self.label = tk.Label(self.root, text="Running in background...")
        self.label.pack(pady=10)

        self.progress = ttk.Progressbar(self.root, length=350, mode="determinate")
        self.progress.pack(pady=10)

        self.status = tk.Label(self.root, text="")
        self.status.pack(pady=5)

        self.stop_event = threading.Event()

        threading.Thread(target=self.background_loop, daemon=True).start()

        self.root.mainloop()

    # ─────────────────────────────
    # NOTIFICATIONS (TRAY STYLE)
    # ─────────────────────────────
    def notify(self, title, msg):
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=msg,
                timeout=5
            )
        except Exception:
            pass

    # ─────────────────────────────
    # BACKGROUND LOOP (24H CHECK)
    # ─────────────────────────────
    def background_loop(self):
        while not self.stop_event.is_set():
            try:
                self.check_update(silent=True)
            except Exception:
                pass

            time.sleep(86400)

    # ─────────────────────────────
    # UPDATE CHECK
    # ─────────────────────────────
    def check_update(self, silent=False):
        r = requests.get(GITHUB_API, timeout=10)
        data = r.json()

        version = data["tag_name"]
        asset = data["assets"][0]

        url = asset["browser_download_url"]
        sha_url = url + ".sha256"

        if not silent:
            ok = messagebox.askyesno(
                "Update Available",
                f"Version {version} available.\nInstall now?"
            )
            if not ok:
                return

        self.run_update(version, url, sha_url)

    # ─────────────────────────────
    # DOWNLOAD
    # ─────────────────────────────
    def download(self, url, path):
        with requests.get(url, stream=True, timeout=15) as r:
            total = int(r.headers.get("content-length", 0))
            downloaded = 0

            with open(path, "wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    if not chunk:
                        continue

                    f.write(chunk)
                    downloaded += len(chunk)

                    if total:
                        pct = int(downloaded * 100 / total)
                        self.progress["value"] = pct
                        self.status.config(text=f"Downloading... {pct}%")
                        self.root.update_idletasks()

    # ─────────────────────────────
    # SHA256 VERIFY
    # ─────────────────────────────
    def verify_sha256(self, file_path, expected):
        h = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)

        return h.hexdigest().strip().lower() == expected.strip().lower()

    def get_sha256(self, url):
        r = requests.get(url, timeout=10)
        return r.text.split()[0].strip()

    # ─────────────────────────────
    # INSTALL PATHS
    # ─────────────────────────────
    def get_install_dir(self):
        if sys.platform.startswith("win"):
            return os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "AirPlayReceiver")
        else:
            return "/opt/airplay-receiver"

    # ─────────────────────────────
    # BACKUP SYSTEM
    # ─────────────────────────────
    def backup_install(self):
        install_dir = self.get_install_dir()
        backup_dir = install_dir + "_backup"

        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

        if os.path.exists(install_dir):
            shutil.copytree(install_dir, backup_dir)

        return backup_dir

    def restore_backup(self, backup_dir):
        install_dir = self.get_install_dir()

        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)

        if os.path.exists(backup_dir):
            shutil.copytree(backup_dir, install_dir)

    # ─────────────────────────────
    # CLOSE OLD APP (OPTIONAL SAFE)
    # ─────────────────────────────
    def close_old(self):
        try:
            if sys.platform.startswith("win"):
                subprocess.call(["taskkill", "/F", "/IM", "AirPlayReceiver.exe"])
            else:
                subprocess.call(["pkill", "-f", "airplay-receiver"])
        except Exception:
            pass

    # ─────────────────────────────
    # INSTALLER RUN
    # ─────────────────────────────
    def run_installer(self, path):
        if sys.platform.startswith("win"):
            return subprocess.Popen([path])
        else:
            os.chmod(path, 0o700)
            return subprocess.Popen([path])

    # ─────────────────────────────
    # RESTART APP
    # ─────────────────────────────
    def restart_app(self):
        try:
            if sys.platform.startswith("win"):
                exe = os.path.join(self.get_install_dir(), "AirPlayReceiver.exe")
            else:
                exe = self.get_install_dir() + "/airplay-receiver"

            subprocess.Popen([exe])
        except Exception:
            pass

    # ─────────────────────────────
    # MAIN UPDATE FLOW
    # ─────────────────────────────
    def run_update(self, version, url, sha_url):
        backup_dir = None

        try:
            import tempfile

            installer = os.path.join(
                tempfile.gettempdir(),
                "AirPlayReceiverInstaller"
            )

            self.notify("AirPlay Receiver", f"Updating to {version}")

            self.label.config(text="Creating backup...")
            backup_dir = self.backup_install()

            self.close_old()

            self.label.config(text="Downloading update...")
            self.download(url, installer)

            self.label.config(text="Verifying update...")
            expected_sha = self.get_sha256(sha_url)

            if not self.verify_sha256(installer, expected_sha):
                raise Exception("SHA256 mismatch")

            self.label.config(text="Installing update...")

            proc = self.run_installer(installer)
            proc.wait()

            if proc.returncode != 0:
                raise Exception("Installer failed")

            self.label.config(text="Update complete")

            self.notify(
                "AirPlay Receiver Updated",
                "Update installed successfully. Restarting..."
            )

            self.restart_app()

        except Exception as e:
            self.status.config(text="Rolling back...")

            if backup_dir:
                self.restore_backup(backup_dir)

            messagebox.showerror("Update failed", str(e))


if __name__ == "__main__":
    UpdaterUI()