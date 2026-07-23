# ClassicSpeech — Page Orientation RC v25

## Purpose

ClassicSpeech RC v25 is an informal, self-installable NVDA add-on release candidate. It retains the same-synth, queue-safe Voice Profile routing from RC v24 and adds an opt-in Page Orientation presentation for ready Browse Mode documents.

## Supported NVDA versions

- Minimum: NVDA 2025.1
- Last tested: NVDA 2026.1

## Page Orientation

Page Orientation is disabled by default. When enabled, it replaces only the initial ready-document title/root/first-line presentation with the selected ClassicSpeech Page Summary.

- With NVDA Automatic Say All off: the summary is spoken.
- With NVDA Automatic Say All on: the summary is followed by native Say All from the initialized caret.
- If the NVDA runtime seam is unavailable, incompatible, or the feature is disabled, ClassicSpeech falls back to native NVDA presentation.
- Browse Mode loading, focus, caret placement, braille, and later navigation remain NVDA-owned.

## Page Summary settings

- The optional Title choice is above the element choices and is off by default.
- When enabled, the normalized document title is spoken naturally before counts, without a literal `Title:` prefix.
- Manual and automatic summaries use the same formatter.

## Voice Profile safety model

- Profiles remain specific to the active synthesizer.
- A profile may use the synth's exposed Voice, Variant, and supported public settings.
- Explicit category overrides are applied after Voice and Variant selection.
- Reset returns the active synth wholly to native NVDA Voice Settings.
- ClassicSpeech never changes the selected synthesizer automatically.

## Installation

1. Download the `.nvda-addon` file and its `.sha256` checksum sidecar.
2. Optionally compare the downloaded file’s SHA-256 with the sidecar.
3. Open the `.nvda-addon` file in Windows Explorer or activate it from your download location.
4. Approve the NVDA installation prompt.
5. Restart NVDA when prompted.

This is a release candidate. Keep a known-good add-on or configuration backup available while evaluating it.

## Verification completed

- Full local ClassicSpeech harness gate passed.
- The GitHub Actions main-branch gate passed: compile, all harnesses, package build, package-member validation, and artifact upload.
- The packaged archive requires `globalPlugins/page_orientation_runtime.py`, preventing the missing-runtime defect from the withdrawn v24 package.
- Live Page Orientation and title behavior should remain subject to final NVDA/browser validation on the target machine.
