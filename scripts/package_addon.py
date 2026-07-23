"""Build a clean, date-named ClassicSpeech NVDA add-on archive.

The public filename is based on the UTC build date, while manifest.ini retains
NVDA's technical add-on version for update compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RUNTIME_FILES = (
    "classicSpeech.py",
    "page_orientation_runtime.py",
)
RUNTIME_DIRECTORIES = ("_speech_core",)
RELEASE_NOTES = "VOICE-PROFILES-RC-V24.md"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        dest="build_date",
        default=datetime.now(UTC).date().isoformat(),
        help="UTC creation date in YYYY-MM-DD format (defaults to today).",
    )
    return parser.parse_args()


def _validate_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise SystemExit(f"Invalid --date {value!r}; use YYYY-MM-DD.") from error


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        archive.write(file_path, (prefix / file_path.relative_to(source)).as_posix())


def main() -> None:
    build_date = _validate_date(_parse_args().build_date)
    package_name = f"ClassicSpeech-{build_date}.nvda-addon"
    package_path = DIST / package_name
    checksum_path = package_path.with_suffix(package_path.suffix + ".sha256")

    manifest = ROOT / "manifest.ini"
    if not manifest.is_file():
        raise SystemExit(f"Missing manifest: {manifest}")

    DIST.mkdir(exist_ok=True)
    package_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest, "manifest.ini")
        for relative_path in RUNTIME_FILES:
            source = ROOT / relative_path
            if not source.is_file():
                raise SystemExit(f"Missing runtime file: {source}")
            archive.write(source, f"globalPlugins/{relative_path}")
        for relative_path in RUNTIME_DIRECTORIES:
            source = ROOT / relative_path
            if not source.is_dir():
                raise SystemExit(f"Missing runtime directory: {source}")
            _add_tree(archive, source, Path("globalPlugins") / relative_path)

        release_notes = ROOT / "docs" / RELEASE_NOTES
        if release_notes.is_file():
            archive.write(release_notes, f"globalPlugins/docs/{RELEASE_NOTES}")

    with zipfile.ZipFile(package_path) as archive:
        invalid_member = archive.testzip()
        if invalid_member:
            raise SystemExit(f"Corrupt ZIP member: {invalid_member}")
        members = set(archive.namelist())
        required = {
            "manifest.ini",
            "globalPlugins/classicSpeech.py",
            "globalPlugins/page_orientation_runtime.py",
        }
        if not required.issubset(members):
            raise SystemExit(f"Missing required package files: {sorted(required - members)}")
        if any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in members):
            raise SystemExit("Package contains Python cache files")

    checksum = hashlib.sha256(package_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{checksum}  {package_name}\n", encoding="ascii")
    print(f"PACKAGE={package_path}")
    print(f"SHA256={checksum}")


if __name__ == "__main__":
    main()
