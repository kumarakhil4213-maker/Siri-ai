#!/usr/bin/env python3
"""Safer restore helper for the SIRI web project."""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKUPS = BASE / "updates" / "backups"
RESTORE_ITEMS = ("server.py", "static", "start.sh", "version.json")


def remove_path(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_path(source, destination):
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def list_backups():
    if not BACKUPS.is_dir():
        print("अभी कोई Backup folder नहीं मिला।")
        return []
    backups = sorted(
        (p for p in BACKUPS.iterdir()
         if p.is_dir() and not p.is_symlink()
         and (p / "BACKUP_COMPLETE.txt").is_file()),
        key=lambda p: p.name,
        reverse=True,
    )
    print("SIRI AVAILABLE BACKUPS:")
    for backup in backups:
        print("-", backup.name)
    return backups


def make_pre_restore_backup():
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final = BACKUPS / f"pre_restore_{stamp}"
    temporary = BACKUPS / f".{final.name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        for item in RESTORE_ITEMS:
            current = BASE / item
            if current.exists() or current.is_symlink():
                copy_path(current, temporary / item)
        (temporary / "BACKUP_COMPLETE.txt").write_text(
            "Pre-restore safety backup\n", encoding="utf-8"
        )
        temporary.rename(final)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return final


def restore(name):
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("Backup का नाम अमान्य है।")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    source = BACKUPS / name
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Backup folder नहीं मिला।")
    if not (source / "BACKUP_COMPLETE.txt").is_file():
        raise ValueError("Backup अधूरा है; Restore रोक दिया गया।")

    # Validate every required item before touching the live project.
    for item in RESTORE_ITEMS:
        saved = source / item
        if not saved.exists() and not saved.is_symlink():
            raise ValueError(f"Backup में {item} नहीं है; Restore रोक दिया गया।")

    safety = make_pre_restore_backup()
    staging = Path(tempfile.mkdtemp(prefix=".siri_restore_", dir=BASE))
    swapped = []

    try:
        staged_root = staging / "new"
        staged_root.mkdir()
        for item in RESTORE_ITEMS:
            copy_path(source / item, staged_root / item)

        previous_root = staging / "previous"
        for item in RESTORE_ITEMS:
            current = BASE / item
            staged = staged_root / item
            previous = previous_root / item
            previous.parent.mkdir(parents=True, exist_ok=True)
            had_current = current.exists() or current.is_symlink()

            if had_current:
                os.replace(current, previous)
            try:
                os.replace(staged, current)
            except Exception:
                if had_current and previous.exists():
                    os.replace(previous, current)
                raise
            swapped.append((current, previous, had_current))

    except Exception:
        # Put the pre-restore live files back if any replacement failed.
        for current, previous, had_current in reversed(swapped):
            if current.exists() or current.is_symlink():
                remove_path(current)
            if had_current and (previous.exists() or previous.is_symlink()):
                os.replace(previous, current)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print("SIRI CODE RESTORED")
    print("Restore से पहले सुरक्षा Backup बनाया गया:", safety.name)
    print("इस स्क्रिप्ट ने ~/jarvis/data को नहीं छुआ।")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 1 or sys.argv[1] == "list":
            list_backups()
        elif len(sys.argv) == 3 and sys.argv[1] == "restore":
            restore(sys.argv[2])
        else:
            print("Usage:")
            print("python rollback.py list")
            print("python rollback.py restore BACKUP_NAME")
            sys.exit(2)
    except Exception as error:
        print("Restore नहीं हुआ:", error)
        sys.exit(1)
