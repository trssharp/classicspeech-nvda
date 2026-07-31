# ClassicSpeech current status and documentation index

This document describes the current `main` baseline and indexes the maintained documentation. It is not a release note or authorization to deploy, package, or merge work.

Historical files under `docs/plans/` and the versioned RC notes preserve original design, validation, and release rationale. They do not describe the current development baseline and must not be treated as active task lists.

## Current `main` baseline

The current automated baseline includes:

- organized General Settings panels, including the native **Spoken object details** checklist and revised Intermediate defaults;
- same-synth Voice Profiles and the Preferences → ClassicSpeech entry points;
- Web / Browse Mode custom Browse and Focus mode messages, preserving native NVDA behavior until a message is configured;
- Page Summary, Page Ready, heading-continuity, and supported Edge notification controls;
- unbound Input Gestures entries for General Settings, Web / Browse Mode Settings, and Voice Profiles;
- conservative Number Processing that preserves combined digit strings such as `5'5`;
- compatibility coverage for both legacy and current NVDA Braille-input source layouts.

This baseline passed the local harness gate and GitHub Actions run #42. It still requires relevant manual NVDA validation before being treated as a release candidate.

## Current boundaries

- Virtual-buffer mutation, synthetic structural lines, and replacement of NVDA's native Browse Mode presentation are not ClassicSpeech add-on work. The supported add-on API has no buffer write path. Any future proposal requires a separately approved NVDA-core design.
- Page-ready orientation is distinct from virtual-buffer manipulation. It must remain additive, current-document scoped, and must not change native buffer contents, selection, caret, Quick Nav, braille, Say All, or structural speech.
- Tooltip behavior is intentionally unchanged. Tooltip timing is not exposed because the current speech routes cannot provide reliable full-token timing.
- `sequence_merger.py` was removed after a repository-wide dependency audit found no active source, test, packaging, or documentation dependency. Do not reintroduce sequence-merging behavior without a defined requirement and focused coverage.

## Documentation map

| Document | Role |
| --- | --- |
| `../README.md` | Current user-facing feature, settings-access, safety, and testing overview. |
| `DEVELOPMENT-WORKFLOW.md` | Source, branch, CI, scratchpad, and live-validation procedure. |
| `VERSIONING.md` | CI artifact and official-release versioning rules. |
| `WEB-BUFFER-LOAD-RESEARCH.md` | Historical NVDA lifecycle research and the no-buffer-mutation boundary. |
| `VOICE-PROFILES-RC-V24.md` | Historical Voice Profiles RC note. |
| `PAGE-ORIENTATION-RC-V25.md` | Historical Page Orientation RC note. |
| `EDGE-NOTIFICATIONS-RC-V26.md` | Historical Edge Notifications RC note. |
| `plans/2026-07-20-web-summary-v0.md` | Historical manual Page Summary design. |
| `plans/2026-07-21-automatic-page-summary-v1.md` | Historical automatic Page Summary design. |
| `plans/2026-07-22-page-orientation-presentation-research.md` | Archived virtual-buffer presentation research; not implementable as an add-on. |
| `plans/2026-07-23-page-load-notifications-v1.md` | Historical Page Ready design. |
| `plans/2026-07-23-edge-notification-controls.md` | Historical Edge notification-controls design. |

When behavior changes, update this status document, the README, and any relevant release note or add-on metadata together. Historical plans and RC notes should be retained for provenance, not duplicated as competing current roadmaps.
