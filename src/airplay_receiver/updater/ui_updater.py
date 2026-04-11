import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import os
import subprocess
import shutil
import time
import requests

GITHUB_API = "https://api.github.com/repos/tiernan1979/Airplay-receiver/releases/latest"


class UpdaterUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AirPlay Receiver Updater")
        self.root.geometry("420x180")
        self.root.resizable(False, False)

        self.label = tk.Label(self.root, text="Checking for updates...")
        self.label.pack(pady=10)

        self.progress = ttk.Progressbar(self.root, length=350, mode="determinate")
        self.progress.pack(pady=10)

        self.status = tk.Label(self.root, text="")
        self.status.pack(pady=5)

        threading.Thread(target=self.run_update, daemon=True).start()

        self.root.mainloop()

    def get_latest(self):
        r = requests.get(GITHUB_API, timeout=10)
        data = r.json()
        return data["tag_name"], data["assets"][0]["browser_download_url"]

    def get_sha256(url_sha):
        r = requests.get(url_sha, timeout=10)
        return r.text.split()[0].strip()

    def download(self, url, path):
        with requests.get(url, stream=True, timeout=15) as r:
            total = int(r.headers.get("content-length", 0))
            downloaded = 0

            with open(path, "wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total:
                        pct = int(downloaded * 100 / total)
                        self.progress["value"] = pct
                        self.status.config(text=f"Downloading... {pct}%")
                        self.root.update_idletasks()

    def backup_install(self):
        install_dir = os.path.join(os.environ["ProgramFiles"], "AirPlayReceiver")
        backup_dir = install_dir + "_backup"

        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

        shutil.copytree(install_dir, backup_dir)
        return backup_dir

    def restore_backup(self, backup_dir):
        install_dir = os.path.join(os.environ["ProgramFiles"], "AirPlayReceiver")

        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)

        shutil.copytree(backup_dir, install_dir)

    def run_update(self):
        try:
            version, url = self.get_latest()
            sha_url = url + ".sha256"

            # ✔ USER CONFIRMATION (ONLY UI CHANGE)
            ok = messagebox.askyesno(
                "Update Available",
                f"Version {version} is available.\n\nInstall now?"
            )

            if not ok:
                return

            installer = os.path.join(os.environ["TEMP"], "AirPlayReceiverSetup.exe")

            self.label.config(text="Downloading update...")

            self.download(url, installer)

            self.label.config(text="Verifying integrity...")

            expected_sha = self.get_sha256(sha_url)

            if not self.verify_sha256(installer, expected_sha):
                raise Exception("SHA256 verification failed")

            self.label.config(text="Installing update...")

            proc = subprocess.Popen([installer])
            proc.wait()

            if proc.returncode != 0:
                raise Exception("Installer failed")

            self.label.config(text="Update complete")

        except Exception as e:
            messagebox.showerror("Update failed", str(e))

if __name__ == "__main__":
    UpdaterUI()