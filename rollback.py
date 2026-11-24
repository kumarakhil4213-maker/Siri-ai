import sys
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKUPS = BASE / "updates" / "backups"

RESTORE_ITEMS = [
    "server.py",
    "static",
    "start.sh",
    "version.json"
]

def list_backups():
    backups = sorted(
        [p for p in BACKUPS.iterdir()
         if p.is_dir() and (p / "BACKUP_COMPLETE.txt").exists()],
        reverse=True
    )
    print("SIRI AVAILABLE BACKUPS:")
    for p in backups:
        print("-", p.name)
    return backups

def restore(name):
    source = BACKUPS / name

    if not source.is_dir() or not (source / "BACKUP_COMPLETE.txt").exists():
        raise ValueError("Valid backup नहीं मिला")

    for item in RESTORE_ITEMS:
        old = source / item
        current = BASE / item

        if not old.exists():
            continue

        if current.is_dir():
            shutil.rmtree(current)

        if old.is_dir():
            shutil.copytree(old, current)
        else:
            shutil.copy2(old, current)

    print("SIRI CODE RESTORED")
    print("Memory data सुरक्षित रखा गया है।")

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] == "list":
        list_backups()
    elif len(sys.argv) == 3 and sys.argv[1] == "restore":
        restore(sys.argv[2])
    else:
        print("Usage:")
        print("python rollback.py list")
        print("python rollback.py restore BACKUP_NAME")
