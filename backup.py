#!/usr/bin/env python3
"""
Anguis Network Management System - Backup Utility
Creates complete backup archives including databases and filesystem artifacts
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AnguisBackup:
    """Complete backup utility for Anguis NMS"""

    SCHEMA_VERSION = "1.0.0"

    # Paths relative to project root
    DB_FILES = [
        "assets.db",
        "arp_cat.db"
    ]

    ARTIFACT_DIRS = [
        "pcng/capture",
        "pcng/fingerprints",
        "pcng/maps",
        "diffs"
    ]

    OPTIONAL_DIRS = [
        "sessions",
        "logs"
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.validate_environment()

    def validate_environment(self):
        """Ensure we're in a valid Anguis project directory"""
        required_markers = ["app", "db_init.py"]

        for marker in required_markers:
            if not (self.project_root / marker).exists():
                raise RuntimeError(
                    f"Invalid Anguis project directory. Missing: {marker}\n"
                    f"Run this script from the Anguis project root."
                )

    def get_table_counts(self, db_path: str) -> Dict[str, int]:
        """Get record counts for all tables"""
        counts = {}
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

        conn.close()
        return counts

    def calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_directory_stats(self, dirpath: Path) -> Dict:
        """Get statistics about a directory"""
        if not dirpath.exists():
            return {"exists": False, "file_count": 0, "total_size": 0}

        file_count = 0
        total_size = 0

        for root, dirs, files in os.walk(dirpath):
            file_count += len(files)
            total_size += sum(
                os.path.getsize(os.path.join(root, f))
                for f in files
            )

        return {
            "exists": True,
            "file_count": file_count,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

    def create_manifest(self, backup_dir: Path, include_captures: bool) -> Dict:
        """Create backup manifest with metadata and checksums"""
        manifest = {
            "backup_metadata": {
                "timestamp": datetime.now().isoformat(),
                "schema_version": self.SCHEMA_VERSION,
                "anguis_version": "alpha-2025.10",
                "include_captures": include_captures,
                "project_root": str(self.project_root)
            },
            "databases": {},
            "artifacts": {},
            "checksums": {}
        }

        # Database info
        for db_file in self.DB_FILES:
            db_path = self.project_root / db_file
            if db_path.exists():
                manifest["databases"][db_file] = {
                    "size_bytes": db_path.stat().st_size,
                    "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2),
                    "tables": self.get_table_counts(str(db_path))
                }

                # Calculate checksum
                backup_db_path = backup_dir / db_file
                if backup_db_path.exists():
                    manifest["checksums"][db_file] = self.calculate_file_hash(backup_db_path)

        # Artifact directory stats
        for artifact_dir in self.ARTIFACT_DIRS:
            if not include_captures and artifact_dir == "capture":
                manifest["artifacts"][artifact_dir] = {"skipped": True}
                continue

            dir_path = self.project_root / artifact_dir
            manifest["artifacts"][artifact_dir] = self.get_directory_stats(dir_path)

        return manifest

    def copy_database_safely(self, db_name: str, dest_dir: Path) -> bool:
        """Copy SQLite database using backup API to handle locks"""
        src_path = self.project_root / db_name
        dest_path = dest_dir / db_name

        if not src_path.exists():
            print(f"  ⚠ Database not found: {db_name}")
            return False

        try:
            # Use SQLite's backup API for safe copying
            src_conn = sqlite3.connect(str(src_path))
            dest_conn = sqlite3.connect(str(dest_path))

            src_conn.backup(dest_conn)

            src_conn.close()
            dest_conn.close()

            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Backed up {db_name} ({size_mb:.2f} MB)")
            return True

        except Exception as e:
            print(f"  ✗ Error backing up {db_name}: {e}")
            return False

    def copy_directory_tree(self, src_name: str, dest_dir: Path,
                            skip_patterns: Optional[List[str]] = None) -> bool:
        """Copy directory tree with optional exclusions"""
        src_path = self.project_root / src_name
        dest_path = dest_dir / src_name

        if not src_path.exists():
            print(f"  ⚠ Directory not found: {src_name} (skipping)")
            return True

        try:
            def ignore_patterns(directory, files):
                if skip_patterns:
                    return [f for f in files if any(p in f for p in skip_patterns)]
                return []

            shutil.copytree(src_path, dest_path, ignore=ignore_patterns)

            stats = self.get_directory_stats(dest_path)
            print(f"  ✓ Backed up {src_name}/ ({stats['file_count']} files, "
                  f"{stats['total_size_mb']:.2f} MB)")
            return True

        except Exception as e:
            print(f"  ✗ Error backing up {src_name}/: {e}")
            return False

    def create_backup(self, output_dir: str, include_captures: bool = True,
                      include_logs: bool = False) -> Tuple[bool, Optional[str]]:
        """Create a complete backup archive"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'anguis_backup_{timestamp}'
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        archive_path = output_path / f"{backup_name}.tar.gz"

        print(f"\n{'=' * 70}")
        print(f"Anguis Backup Utility")
        print(f"{'=' * 70}")
        print(f"Project Root: {self.project_root}")
        print(f"Output: {archive_path}")
        print(f"Include Captures: {include_captures}")
        print(f"Include Logs: {include_logs}")
        print(f"{'=' * 70}\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / backup_name
            backup_dir.mkdir()

            print("Stage 1: Backing up databases...")
            db_success = True
            for db_file in self.DB_FILES:
                if not self.copy_database_safely(db_file, backup_dir):
                    db_success = False

            if not db_success:
                print("\n✗ Database backup failed")
                return False, None

            print("\nStage 2: Backing up artifact directories...")

            # Always backup these
            for artifact_dir in ["diffs"]:
                self.copy_directory_tree(artifact_dir, backup_dir)

            # Handle pcng subdirectory structure
            for artifact_dir in ["pcng/fingerprints", "pcng/maps", "pcng/capture"]:
                if include_captures or artifact_dir != "pcng/capture":
                    self.copy_directory_tree(artifact_dir, backup_dir)
                elif artifact_dir == "pcng/capture":
                    print("  ⊘ Skipping pcng/capture/ (--no-captures specified)")

            if include_logs:
                self.copy_directory_tree("logs", backup_dir,
                                         skip_patterns=['.tmp', '.lock'])

            print("\nStage 3: Generating manifest...")
            manifest = self.create_manifest(backup_dir, include_captures)

            manifest_path = backup_dir / "backup_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            print(f"  ✓ Created manifest")

            print("\nStage 4: Creating compressed archive...")
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=backup_name)

            archive_size = archive_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Archive created ({archive_size:.2f} MB)")

        print(f"\n{'=' * 70}")
        print(f"✓ Backup completed successfully")
        print(f"{'=' * 70}")
        print(f"Archive: {archive_path}")
        print(f"Size: {archive_size:.2f} MB")

        # Print summary
        if "databases" in manifest:
            total_devices = manifest["databases"].get("assets.db", {}).get(
                "tables", {}).get("devices", 0)
            total_components = manifest["databases"].get("assets.db", {}).get(
                "tables", {}).get("components", 0)
            print(f"\nBackup Contents:")
            print(f"  Devices: {total_devices}")
            print(f"  Components: {total_components}")

            if "artifacts" in manifest and "capture" in manifest["artifacts"]:
                captures = manifest["artifacts"]["capture"]
                if captures.get("exists"):
                    print(f"  Capture Files: {captures['file_count']} "
                          f"({captures['total_size_mb']:.2f} MB)")

        print(f"{'=' * 70}\n")

        return True, str(archive_path)


def main():
    parser = argparse.ArgumentParser(
        description="Anguis Network Management System - Backup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full backup with everything
  python backup.py --output ./backups

  # Metadata-only backup (excludes large capture files)
  python backup.py --output ./backups --no-captures

  # Full backup with logs
  python backup.py --output ./backups --include-logs

  # Backup from specific project directory
  python backup.py --project-root /path/to/anguis --output ./backups
        """
    )

    parser.add_argument(
        '--project-root',
        default='.',
        help='Anguis project root directory (default: current directory)'
    )

    parser.add_argument(
        '--output',
        default='./backups',
        help='Output directory for backup archive (default: ./backups)'
    )

    parser.add_argument(
        '--no-captures',
        action='store_true',
        help='Exclude capture files (creates smaller metadata-only backup)'
    )

    parser.add_argument(
        '--include-logs',
        action='store_true',
        help='Include log files in backup'
    )

    args = parser.parse_args()

    try:
        backup = AnguisBackup(args.project_root)
        success, archive_path = backup.create_backup(
            args.output,
            include_captures=not args.no_captures,
            include_logs=args.include_logs
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n✗ Backup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()