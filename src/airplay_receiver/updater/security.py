import hashlib
import requests

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(file_path, expected):
    return sha256_file(file_path).lower() == expected.lower()


def get_sha256(url):
    r = requests.get(url, timeout=5)
    return r.text.split()[0].strip()