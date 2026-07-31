# Historical: ClassicSpeech Voice Profiles — RC v24

> This is a preserved RC v24 release note. It is not the current release candidate or the current `main` feature reference. See `../README.md` and `ROADMAP-STATUS.md` for the current baseline.

## Purpose

ClassicSpeech RC v24 is an informal, self-installable NVDA add-on release candidate. It provides same-synth, queue-safe Voice Profile routing for chosen ClassicSpeech speech categories while restoring the active NVDA synth settings after each owned sequence.

## Supported NVDA versions

- Minimum: NVDA 2025.1
- Last tested: NVDA 2026.1

## Voice Profile categories

1. **Focus and navigation** — normal ClassicSpeech-formatted focus and navigation speech.
2. **Review and object navigation** — Review Cursor, navigator-object status, and mouse feedback.
3. **Keyboard entry** — typed characters and words; braille only when it uses NVDA's shared typed-entry path.
4. **System and notifications** — explicitly scoped system-origin speech, including incoming Windows toast events when NVDA receives them.

## Settings and safety model

- Profiles are specific to the active synthesizer.
- A profile may use the synth's exposed Voice, Variant, and supported public settings.
- Explicit category overrides are applied after Voice and Variant selection.
- The configured native NVDA Rate carries through Voice/Variant changes unless a category explicitly overrides Rate.
- Reset returns the active synth wholly to native NVDA Voice Settings.
- ClassicSpeech never changes the selected synthesizer automatically.
- Automatic cross-synth switching is deliberately out of scope.

## v24 additions and corrections

- Restored and verified scoped System routing for incoming Windows notifications. Windows may place some notifications in Notification Center without delivering a live accessibility event to NVDA; that source behavior is outside ClassicSpeech.
- Corrected NVDA Remote handling for profile-trigger commands when Remote was connected before ClassicSpeech loaded. Local Voice Profile routing remains intact; only the Remote copy omits local-only trigger commands.
- Added per-profile Position announcement defaults:
  - Beginner: announce on every move.
  - Intermediate: announce only the first item in a container.
  - Advanced: off.
- Preserved the Position/Hotkey semantic pause behavior and system-profile restoration.

## Installation

1. Download the `.nvda-addon` file.
2. Open it in Windows Explorer or activate it from your download location.
3. Approve the NVDA installation prompt.
4. Restart NVDA when prompted.

This is a release candidate. Keep a known-good add-on or configuration backup available while evaluating it.

## Verification completed

- Full ClassicSpeech harness gate passed.
- Runtime compilation passed.
- Scratchpad deployment source/runtime comparison passed.
- Live System-toast validation confirmed correct System profile entry, IBM TTS Variant application/restoration, and clean NVDA Remote transport after v24 reload.
