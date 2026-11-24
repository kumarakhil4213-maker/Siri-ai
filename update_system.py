import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
BACKUP_DIR = BASE / "updates" / "backups"
VERSION_FILE = BASE / "version.json"

def get_version():
    if not VERSION_FILE.exists():
        VERSION_FILE.write_text(
            json.dumps({"version": "1.0.0"}, indent=2),
            encoding="utf-8"
        )
    return json.loads(VERSION_FILE.read_text(encoding="utf-8"))

def create_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = "siri_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / name
    target.mkdir()

    items = [
        "server.py",
        "server.py.backup",
        "static",
        "data",
        "start.sh",
        "update_system.py",
        "rollback.py",
        "check_update.py",
        "version.json"
    ]

    try:
        for name in items:
            source = BASE / name
            destination = target / name

            if not source.exists():
                continue

            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)

        (target / "BACKUP_COMPLETE.txt").write_text(
            "SIRI backup completed successfully.\n",
            encoding="utf-8"
        )

        manifest = {}
        for file in sorted(target.rglob("*")):
            if file.is_file() and file.name != "SHA256SUMS.json":
                relative = file.relative_to(target).as_posix()
                manifest[relative] = hashlib.sha256(file.read_bytes()).hexdigest()

        (target / "SHA256SUMS.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8"
        )
        return str(target)

    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

def verify_backup(backup_path):
    target = Path(backup_path)
    if not target.is_absolute() and not target.exists():
        target = BACKUP_DIR / target

    try:
        if not (target / "BACKUP_COMPLETE.txt").is_file():
            return False

        manifest = json.loads(
            (target / "SHA256SUMS.json").read_text(encoding="utf-8")
        )

        if not isinstance(manifest, dict) or not manifest:
            return False

        for name, expected in manifest.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                return False

            file = target / relative
            if not file.is_file():
                return False

            actual = hashlib.sha256(file.read_bytes()).hexdigest()
            if actual != expected:
                return False

        return True
    except (OSError, ValueError, TypeError):
        return False


if __name__ == "__main__":
    print("SIRI VERSION:", get_version()["version"])
    print("BACKUP:", create_backup())
    print("SIRI UPDATE SYSTEM READY")
