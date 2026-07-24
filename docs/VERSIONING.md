# ClassicSpeech versioning and CI artifact identity

## Version schema

ClassicSpeech uses a numeric three-part manifest version:

```text
MAJOR.MINOR.PATCH
```

This is intentionally plain numeric data because current NVDA Add-on Store logic parses side-loaded add-on versions as two or three integers. A nonnumeric version makes automatic update ordering unknown.

- **MAJOR** changes for incompatible add-on behavior or storage migration.
- **MINOR** changes for a compatible feature release.
- **PATCH** changes for a compatible bug fix or release-candidate progression.

The Edge release candidate in this branch is **4.0.26**. Future compatible candidates advance the numeric version; do not encode a feature name or `rc` text in `manifest.ini`.

## Release channels

The Git tag—not `manifest.ini`—expresses the channel:

```text
v4.0.26          stable release
v4.0.26-rc.1     first release candidate
v4.0.26-rc.2     second release candidate
```

The GitHub Actions workflow rejects a tag that does not match the current manifest version.

## Artifact names

Every artifact begins with the manifest version. CI appends a channel/build identity and UTC date:

```text
ClassicSpeech-4.0.26-rc.1-2026-07-24.nvda-addon
ClassicSpeech-4.0.26-dev.30114390474-gdbdd07b-2026-07-24.nvda-addon
```

- A matching `vMAJOR.MINOR.PATCH` tag produces a stable artifact with no channel label.
- A matching `vMAJOR.MINOR.PATCH-rc.N` tag produces an `rc.N` artifact.
- A branch or manually dispatched workflow produces a non-release `dev.<run>-g<shortSHA>` artifact.

The accompanying `.sha256` sidecar uses the same basename. Do not publish a `dev` artifact as a release.