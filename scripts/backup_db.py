#!/usr/bin/env python3
"""Database backup script for ContentMultiplier.

Usage:
    python scripts/backup_db.py                  # Manual backup
    python scripts/backup_db.py --restore latest  # Restore latest backup
    python scripts/backup_db.py --restore 2024-01-15_10-30-00  # Restore specific backup

Schedule with cron:
    0 */4 * * * cd /path/to/content_creation_engine && python scripts/backup_db.py
"""
import shutil
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
import gzip

# Paths
BASE_DIR = Path(__file__).parent.parent
DATABASE_DIR = BASE_DIR / "database"
BACKUP_DIR = BASE_DIR / "backups"
DB_PATH = DATABASE_DIR / "contentmultiplier.db"

# Keep last N backups
MAX_BACKUPS = 10


def create_backup():
    """Create a compressed backup of the database."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return None

    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{timestamp}.db.gz"
    backup_path = BACKUP_DIR / backup_name

    # Create SQLite backup using backup API (safer than file copy)
    temp_backup = BACKUP_DIR / f"temp_{timestamp}.db"

    try:
        # Connect to source and destination
        source_conn = sqlite3.connect(DB_PATH)
        dest_conn = sqlite3.connect(temp_backup)

        # Use SQLite backup API
        with dest_conn:
            source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()

        # Compress the backup
        with open(temp_backup, "rb") as f_in:
            with gzip.open(backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove temp file
        temp_backup.unlink()

        # Get backup size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"Backup created: {backup_name} ({size_mb:.2f} MB)")

        # Clean up old backups
        cleanup_old_backups()

        return backup_path

    except Exception as e:
        print(f"Backup failed: {e}")
        if temp_backup.exists():
            temp_backup.unlink()
        return None


def cleanup_old_backups():
    """Remove old backups keeping only the most recent ones."""
    backups = sorted(BACKUP_DIR.glob("backup_*.db.gz"), reverse=True)

    if len(backups) > MAX_BACKUPS:
        for old_backup in backups[MAX_BACKUPS:]:
            print(f"Removing old backup: {old_backup.name}")
            old_backup.unlink()


def list_backups():
    """List all available backups."""
    if not BACKUP_DIR.exists():
        print("No backups found.")
        return []

    backups = sorted(BACKUP_DIR.glob("backup_*.db.gz"), reverse=True)

    if not backups:
        print("No backups found.")
        return []

    print("Available backups:")
    for backup in backups:
        size_mb = backup.stat().st_size / (1024 * 1024)
        # Extract timestamp from filename
        name = backup.stem.replace("backup_", "").replace(".db", "")
        print(f"  {name} ({size_mb:.2f} MB)")

    return backups


def restore_backup(backup_name: str):
    """Restore database from a backup."""
    if backup_name == "latest":
        backups = sorted(BACKUP_DIR.glob("backup_*.db.gz"), reverse=True)
        if not backups:
            print("No backups found.")
            return False
        backup_path = backups[0]
    else:
        backup_path = BACKUP_DIR / f"backup_{backup_name}.db.gz"
        if not backup_path.exists():
            print(f"Backup not found: {backup_path}")
            return False

    print(f"Restoring from: {backup_path.name}")

    # Create a backup of current database before restoring
    if DB_PATH.exists():
        current_backup = DATABASE_DIR / "pre_restore_backup.db"
        shutil.copy2(DB_PATH, current_backup)
        print(f"Current database backed up to: {current_backup}")

    try:
        # Decompress backup
        temp_restore = BACKUP_DIR / "temp_restore.db"
        with gzip.open(backup_path, "rb") as f_in:
            with open(temp_restore, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Replace current database
        shutil.move(temp_restore, DB_PATH)
        print(f"Database restored successfully.")
        return True

    except Exception as e:
        print(f"Restore failed: {e}")
        if temp_restore.exists():
            temp_restore.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="ContentMultiplier Database Backup Tool")
    parser.add_argument("--restore", type=str, help="Restore from backup (use 'latest' or timestamp)")
    parser.add_argument("--list", action="store_true", help="List available backups")

    args = parser.parse_args()

    if args.list:
        list_backups()
    elif args.restore:
        restore_backup(args.restore)
    else:
        create_backup()


if __name__ == "__main__":
    main()
