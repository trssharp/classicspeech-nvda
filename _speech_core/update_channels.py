"""Public development release identity and installed-build provenance."""
import json
import re
from datetime import datetime
from pathlib import Path

OFFICIAL_REPOSITORY = "trssharp/classicspeech-nvda"
METADATA_PATH = Path(__file__).with_name("build_info.json")
_DEV_VERSION = re.compile(r"[0-9]{8}\.[1-9][0-9]*")


def dev_version(tag):
    """Official tags are dev-YYYYMMDD.RUN, never an arbitrary prerelease."""
    if not isinstance(tag, str) or not tag.startswith("dev-"):
        return None
    version = tag[4:]
    if not _DEV_VERSION.fullmatch(version):
        return None
    try:
        datetime.strptime(version[:8], "%Y%m%d")
    except ValueError:
        return None
    return version


def official_dev_assets(data, repository, version):
    if repository != OFFICIAL_REPOSITORY:
        return False
    name = f"ClassicSpeech-{version}.nvda-addon"
    prefix = f"https://github.com/{repository}/releases/download/dev-{version}/"
    assets = data.get("assets")
    if not isinstance(assets, list):
        return False
    for wanted in (name, name + ".sha256"):
        matches = [a for a in assets if isinstance(a, dict) and a.get("name") == wanted]
        if len(matches) != 1 or matches[0].get("browser_download_url") != prefix + wanted:
            return False
    return data.get("html_url") == f"https://github.com/{repository}/releases/tag/dev-{version}"


def default_update_channel():
    """Default only: trust packaged, version-matched metadata, never version shape.

    Scratchpad, legacy and unreadable/unknown builds stay on stable. This is
    evaluated when registering the schema, not on every preference read.
    """
    from configobj import ConfigObj, ConfigObjError

    try:
        data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        manifest = ConfigObj(str(METADATA_PATH.parents[2] / "manifest.ini"),
                             encoding="utf-8", file_error=True, interpolation=False)
        version = data.get("version")
        if (data.get("channel") == "dev" and isinstance(version, str)
                and version and manifest.get("version") == version):
            return "dev"
    except (OSError, ValueError, TypeError, AttributeError, ConfigObjError):
        pass
    return "stable"


def installed_channel(version):
    """Metadata describes the installed artifact, never the user's preference.

    Old numeric release versions are stable. Old date/run artifacts have no
    channel provenance: only a manual check may offer a channel transition.
    """
    try:
        data = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        if data.get("version") == version and data.get("channel") in ("stable", "dev", "unknown"):
            return data["channel"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return "unknown" if re.match(r"^[0-9]{8}\.", version) else "stable"
