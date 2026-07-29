"""Build a clean ClassicSpeech NVDA add-on with a generated numeric build version."""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RUNTIME_FILES = ("classicSpeech.py",)
RUNTIME_DIRECTORIES = ("_speech_core",)
APP_MODULE_DIRECTORIES = ("appModules",)
RELEASE_NOTES = "EDGE-NOTIFICATIONS-RC-V26.md"
_NUMERIC_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Numeric package version, e.g. 20260724.16.")
    parser.add_argument(
        "--label",
        default="",
        help="Optional safe build label, normally g followed by the commit short SHA.",
    )
    return parser.parse_args()


def build_version(utc_date: str, run_number: str) -> str:
    """Return an NVDA-comparable, chronological CI version from UTC date and run."""
    try:
        day = datetime.strptime(utc_date, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError as error:
        raise ValueError(f"Date must use YYYY-MM-DD: {utc_date!r}") from error
    if not run_number.isdecimal() or int(run_number) < 1:
        raise ValueError(f"Run number must be a positive integer: {run_number!r}")
    return f"{day}.{int(run_number)}"


def package_filename(version: str, label: str = "") -> str:
    """Build the public package filename from generated version and commit label."""
    if not _NUMERIC_VERSION.fullmatch(version):
        raise ValueError(f"Version must use numeric components: {version!r}")
    if label and not _SAFE_LABEL.fullmatch(label):
        raise ValueError(f"Label is not safe for an artifact filename: {label!r}")
    suffix = f"-{label}" if label else ""
    return f"ClassicSpeech-{version}{suffix}.nvda-addon"


def manifest_with_version(manifest: Path, version: str) -> str:
    """Produce the package-only manifest; source stays on its neutral placeholder."""
    if not _NUMERIC_VERSION.fullmatch(version):
        raise ValueError(f"Version must use numeric components: {version!r}")
    source = manifest.read_text(encoding="utf-8")
    packaged, replacements = re.subn(r"(?m)^(\s*version\s*=\s*).*$", rf"\g<1>{version}", source)
    if replacements != 1:
        raise ValueError("manifest.ini must contain exactly one version entry")
    return packaged


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        archive.write(file_path, (prefix / file_path.relative_to(source)).as_posix())


def main() -> None:
    args = _parse_args()
    manifest = ROOT / "manifest.ini"
    if not manifest.is_file():
        raise SystemExit(f"Missing manifest: {manifest}")
    version = args.version
    package_name = package_filename(version, args.label)
    package_path = DIST / package_name
    checksum_path = package_path.with_suffix(package_path.suffix + ".sha256")

    DIST.mkdir(exist_ok=True)
    package_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.ini", manifest_with_version(manifest, version))
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
            "globalPlugins/_speech_core/processors/web/page_entry.py",
            "globalPlugins/_speech_core/settings/text/__init__.py",
            "globalPlugins/_speech_core/settings/text/config.py",
            "globalPlugins/_speech_core/settings/text/panel.py",
            "appModules/msedge.py",
        }
        if not required.issubset(members):
            raise SystemExit(f"Missing required package files: {sorted(required - members)}")
        if "globalPlugins/page_orientation_runtime.py" in members:
            raise SystemExit("Package contains loose Page Orientation runtime")
        obsolete_text_members = {
            "globalPlugins/_speech_core/settings/text_processing_config.py",
            "globalPlugins/_speech_core/settings/text_processing_panel.py",
        }
        if obsolete_text_members & members:
            raise SystemExit("Package contains obsolete flat Text Processing settings modules")
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
