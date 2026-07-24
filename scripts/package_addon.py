"""Build a clean ClassicSpeech NVDA add-on archive named from its manifest version.

The public filename includes both the technical NVDA add-on version and UTC
build date so a downloaded artifact identifies the installed release.
"""
from __future__ import annotations

import argparse
import hashlib
import re
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
APP_MODULE_DIRECTORIES = ("appModules",)
RELEASE_NOTES = "EDGE-NOTIFICATIONS-RC-V26.md"
_NUMERIC_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        dest="build_date",
        default=datetime.now(UTC).date().isoformat(),
        help="UTC creation date in YYYY-MM-DD format (defaults to today).",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Optional safe build label, such as rc.1 or dev.123-gabcdef0.",
    )
    return parser.parse_args()


def _validate_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise SystemExit(f"Invalid --date {value!r}; use YYYY-MM-DD.") from error


def get_manifest_version(manifest: Path) -> str:
    """Return the manifest version without accepting ambiguous artifact names."""
    for line in manifest.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip().casefold() == "version":
            version = value.strip()
            if _NUMERIC_VERSION.fullmatch(version):
                return version
            raise ValueError(f"Manifest version must use MAJOR.MINOR.PATCH: {version!r}")
    raise ValueError("manifest.ini has no version entry")


def package_filename(version: str, build_date: str, label: str = "") -> str:
    """Build the public package filename from version, optional channel, and UTC date."""
    if not _NUMERIC_VERSION.fullmatch(version):
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH: {version!r}")
    if label and not _SAFE_LABEL.fullmatch(label):
        raise ValueError(f"Label is not safe for an artifact filename: {label!r}")
    channel = f"-{label}" if label else ""
    return f"ClassicSpeech-{version}{channel}-{_validate_date(build_date)}.nvda-addon"


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        archive.write(file_path, (prefix / file_path.relative_to(source)).as_posix())


def main() -> None:
    args = _parse_args()
    build_date = _validate_date(args.build_date)
    manifest = ROOT / "manifest.ini"
    if not manifest.is_file():
        raise SystemExit(f"Missing manifest: {manifest}")
    version = get_manifest_version(manifest)
    package_name = package_filename(version, build_date, args.label)
    package_path = DIST / package_name
    checksum_path = package_path.with_suffix(package_path.suffix + ".sha256")

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
        for relative_path in APP_MODULE_DIRECTORIES:
            source = ROOT / relative_path
            if not source.is_dir():
                raise SystemExit(f"Missing app module directory: {source}")
            _add_tree(archive, source, Path(relative_path))

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
            "appModules/msedge.py",
        }
        if not required.issubset(members):
            raise SystemExit(f"Missing required package files: {sorted(required - members)}")
        if any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in members):
            raise SystemExit("Package contains Python cache files")

    checksum = hashlib.sha256(package_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{checksum}  {package_name}\n", encoding="ascii")
    print(f"PACKAGE_VERSION={version}")
    print(f"PACKAGE_NAME={package_name}")
    print(f"PACKAGE={package_path}")
    print(f"SHA256={checksum}")


if __name__ == "__main__":
    main()
