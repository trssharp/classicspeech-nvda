"""Compose manual prerelease notes from the pinned checkout, without publishing."""
import argparse
from pathlib import Path

from .package_addon import build_metadata, development_whats_new


def release_body(version: str, commit: str) -> str:
    build_metadata(version, "dev", commit)
    return (
        f"# Development build {version}\n\nSource commit: {commit}\n\n"
        "Experimental dev build, not a stable release.\n\n"
        f"## What's new\n\n{development_whats_new()}\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(release_body(args.version, args.commit), encoding="utf-8")


if __name__ == "__main__":
    main()
