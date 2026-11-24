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
        return str(target)

    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

if __name__ == "__main__":
    print("SIRI VERSION:", get_version()["version"])
    print("BACKUP:", create_backup())
    print("SIRI UPDATE SYSTEM READY")
