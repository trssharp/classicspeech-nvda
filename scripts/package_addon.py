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
# NVDA runs installTasks.py from the add-on root when the add-on is installed or removed.
ROOT_FILES = ("installTasks.py",)
RUNTIME_DIRECTORIES = ("_speech_core",)
APP_MODULE_DIRECTORIES = ("appModules",)
# NVDA's Add-on Store Help opens doc/<language>/<docFileName> from the add-on root.
DOC_DIRECTORIES = ("doc",)
LOCALE_DIRECTORIES = ("locale",)
RELEASE_NOTES = "RELEASE-2.0.md"
# NVDA 2026.1 and later show the manifest's changelog, rendered from Markdown, when you choose
# "What's new" for an add-on in the Add-on Store. Every release's changelog is this section of
# its release notes; --sync-changelog copies it into manifest.ini.
WHATS_NEW_HEADING = "## What's new"
_NUMERIC_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
# The version build_version generates for a CI build. Any other version is a release.
_CI_BUILD_VERSION = re.compile(r"^\d{8}\.\d+$")
_RELEASE_NOTES_NAME = re.compile(r"^RELEASE-(\d+\.\d+(?:\.\d+)?)\.md$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# The changelog is a triple-quoted value, the only way a manifest value can span lines.
_CHANGELOG_BLOCK = re.compile(r'(?ms)^[ \t]*changelog[ \t]*=[ \t]*"""(.*?)"""[ \t]*\r?(?:\n|\Z)')
_CHANGELOG_KEY = re.compile(r"(?m)^[ \t]*changelog[ \t]*=")
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})[ \t]")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--version",
        help="Numeric package version, e.g. 20260724.16. A release version, such as 1.02, must be the"
        " version of RELEASE_NOTES.",
    )
    mode.add_argument(
        "--sync-changelog",
        action="store_true",
        help=f"Copy the {WHATS_NEW_HEADING!r} section of docs/{RELEASE_NOTES} into the changelog of"
        " manifest.ini, then exit without packaging.",
    )
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
    # A changelog line is text, not a key, even when it happens to start with "version =".
    changelog = _CHANGELOG_BLOCK.search(source)
    start, end = changelog.span() if changelog else (len(source), len(source))
    pattern, replacement = r"(?m)^(\s*version\s*=\s*).*$", rf"\g<1>{version}"
    head, head_replacements = re.subn(pattern, replacement, source[:start])
    tail, tail_replacements = re.subn(pattern, replacement, source[end:])
    if head_replacements + tail_replacements != 1:
        raise ValueError("manifest.ini must contain exactly one version entry")
    return head + source[start:end] + tail


def manifest_doc_file_name(manifest_text: str) -> str | None:
    """Return the manifest's docFileName, the guide NVDA's Add-on Store Help opens."""
    keys = _CHANGELOG_BLOCK.sub("", manifest_text)
    match = re.search(r'(?m)^\s*docFileName\s*=\s*"?([^"\r\n]*?)"?\s*$', keys)
    if match is None or not match.group(1).strip():
        return None
    return match.group(1).strip()


def manifest_changelog(manifest_text: str) -> str | None:
    """Return the manifest's changelog as NVDA's manifest reader (ConfigObj) sees it."""
    match = _CHANGELOG_BLOCK.search(manifest_text.replace("\r\n", "\n"))
    return match.group(1) if match else None


def check_changelog(changelog: str) -> None:
    """Refuse a changelog that a triple-quoted manifest value can't hold unchanged."""
    if not changelog.strip():
        raise ValueError("The changelog is empty")
    if '"""' in changelog:
        raise ValueError('The changelog must not contain """, which would end it early')
    if "%(" in changelog:
        # ConfigObj reads %(name)s as a reference to another value and fails when there is none.
        raise ValueError("The changelog must not contain %(, which NVDA's manifest reader treats as a reference")


def manifest_with_changelog(manifest_text: str, changelog: str) -> str:
    """Return the manifest with its changelog replaced, or added at the end if it has none."""
    check_changelog(changelog)
    block = f'changelog = """{changelog}"""\n'
    match = _CHANGELOG_BLOCK.search(manifest_text)
    if match is not None:
        return manifest_text[: match.start()] + block + manifest_text[match.end():]
    if _CHANGELOG_KEY.search(manifest_text):
        raise ValueError('manifest.ini has a changelog that is not a triple-quoted ("""...""") value')
    return manifest_text.rstrip("\n") + "\n" + block


def release_whats_new(notes_text: str) -> str | None:
    """Return the What's new section of release notes, the manifest changelog for that release.

    It runs from WHATS_NEW_HEADING to the next heading of level one or two, so it may have
    headings of its own from level three down.
    """
    lines = notes_text.replace("\r\n", "\n").split("\n")
    start = next((index + 1 for index, line in enumerate(lines) if line.strip() == WHATS_NEW_HEADING), None)
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        heading = _MARKDOWN_HEADING.match(lines[index])
        if heading is not None and len(heading.group(1)) <= 2:
            end = index
            break
    return "\n".join(lines[start:end]).strip() or None


def release_notes_version(name: str) -> str | None:
    """Return the version a release notes file is for, from its RELEASE-<version>.md name."""
    match = _RELEASE_NOTES_NAME.fullmatch(name)
    return match.group(1) if match else None


def sync_changelog(manifest: Path, release_notes: Path) -> bool:
    """Make the manifest's changelog the release notes' What's new; return whether it changed."""
    whats_new = release_whats_new(release_notes.read_text(encoding="utf-8"))
    if whats_new is None:
        raise ValueError(f"{release_notes.name} has no {WHATS_NEW_HEADING!r} section")
    raw = manifest.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    updated = manifest_with_changelog(text, whats_new)
    if updated == text:
        return False
    manifest.write_text(updated, encoding="utf-8", newline=newline)
    return True


def check_release_changelog(manifest_text: str, release_notes: Path, version: str) -> None:
    """Refuse to package without this release's What's new in the manifest changelog."""
    if not release_notes.is_file():
        raise ValueError(f"Missing release notes: {release_notes}")
    if not _CI_BUILD_VERSION.fullmatch(version) and release_notes_version(release_notes.name) != version:
        raise ValueError(
            f"Release {version} needs its own release notes, but RELEASE_NOTES is {release_notes.name}."
            f" Add docs/RELEASE-{version}.md with a {WHATS_NEW_HEADING!r} section, point RELEASE_NOTES"
            " at it and run: python scripts/package_addon.py --sync-changelog"
        )
    whats_new = release_whats_new(release_notes.read_text(encoding="utf-8"))
    if whats_new is None:
        raise ValueError(
            f"{release_notes.name} has no {WHATS_NEW_HEADING!r} section to use as the manifest changelog"
        )
    check_changelog(whats_new)
    if manifest_changelog(manifest_text) != whats_new:
        raise ValueError(
            f"The changelog in manifest.ini is not the What's new section of {release_notes.name}."
            " Run: python scripts/package_addon.py --sync-changelog"
        )


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        archive.write(file_path, (prefix / file_path.relative_to(source)).as_posix())


def _add_locale_tree(archive: zipfile.ZipFile, source: Path) -> None:
    """Package runtime catalogs while excluding editable PO/POT sources."""
    for file_path in sorted(source.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix != ".mo" and file_path.name != "manifest.ini":
            continue
        archive.write(file_path, (Path("locale") / file_path.relative_to(source)).as_posix())


def main() -> None:
    args = _parse_args()
    manifest = ROOT / "manifest.ini"
    if not manifest.is_file():
        raise SystemExit(f"Missing manifest: {manifest}")
    release_notes = ROOT / "docs" / RELEASE_NOTES
    if args.sync_changelog:
        try:
            changed = sync_changelog(manifest, release_notes)
        except (OSError, ValueError) as error:
            raise SystemExit(str(error)) from error
        print(f"CHANGELOG={'updated' if changed else 'unchanged'} from docs/{RELEASE_NOTES}")
        return
    version = args.version
    package_name = package_filename(version, args.label)
    try:
        check_release_changelog(manifest.read_text(encoding="utf-8"), release_notes, version)
    except ValueError as error:
        raise SystemExit(str(error)) from error
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
        for relative_path in ROOT_FILES:
            source = ROOT / relative_path
            if not source.is_file():
                raise SystemExit(f"Missing add-on root file: {source}")
            archive.write(source, relative_path)
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
        for relative_path in DOC_DIRECTORIES:
            source = ROOT / relative_path
            if not source.is_dir():
                raise SystemExit(f"Missing documentation directory: {source}")
            _add_tree(archive, source, Path(relative_path))
        for relative_path in LOCALE_DIRECTORIES:
            source = ROOT / relative_path
            if source.is_dir():
                _add_locale_tree(archive, source)

        archive.write(release_notes, f"globalPlugins/docs/{RELEASE_NOTES}")

    with zipfile.ZipFile(package_path) as archive:
        invalid_member = archive.testzip()
        if invalid_member:
            raise SystemExit(f"Corrupt ZIP member: {invalid_member}")
        members = set(archive.namelist())
        required = {
            "manifest.ini",
            "installTasks.py",
            "globalPlugins/classicSpeech.py",
            "globalPlugins/_speech_core/nvda_settings_backup.py",
            "globalPlugins/_speech_core/settings_file.py",
            "globalPlugins/_speech_core/processors/web/page_entry.py",
            "globalPlugins/_speech_core/settings/text/__init__.py",
            "globalPlugins/_speech_core/settings/text/config.py",
            "globalPlugins/_speech_core/settings/text/panel.py",
            "globalPlugins/_speech_core/focus_ancestry.py",
            "globalPlugins/_speech_core/schemes/__init__.py",
            "globalPlugins/_speech_core/schemes/catalog.py",
            "globalPlugins/_speech_core/schemes/labels.py",
            "globalPlugins/_speech_core/schemes/markers.py",
            "globalPlugins/_speech_core/schemes/packages.py",
            "globalPlugins/_speech_core/schemes/runtime.py",
            "globalPlugins/_speech_core/schemes/store.py",
            "globalPlugins/_speech_core/schemes/tagging.py",
            "globalPlugins/_speech_core/settings/schemes_dialog.py",
            "globalPlugins/_speech_core/settings/schemes_panel.py",
            "globalPlugins/_speech_core/settings/file_choosers.py",
            "globalPlugins/_speech_core/settings/voice_profile_packages.py",
            "globalPlugins/_speech_core/user_guide.py",
            "appModules/msedge.py",
            "locale/es/LC_MESSAGES/nvda.mo",
        }
        doc_file_name = manifest_doc_file_name(manifest.read_text(encoding="utf-8"))
        if doc_file_name is None:
            raise SystemExit("manifest.ini must name the user guide in docFileName")
        required.add(f"doc/en/{doc_file_name}")
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
