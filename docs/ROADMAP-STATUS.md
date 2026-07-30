# ClassicSpeech roadmap status

This is the current documentation index for roadmap work. Historical files under `docs/plans/` preserve their original design and test rationale; they are not active task lists and must not be treated as authorization to implement, deploy, package, or merge work.

## Current boundaries

- Virtual-buffer mutation, synthetic structural lines, and replacement of NVDA's native Browse Mode presentation are not ClassicSpeech add-on work. The supported add-on API has no buffer write path. Any future proposal requires a separately approved NVDA-core design.
- Page-ready orientation is distinct from virtual-buffer manipulation. It must remain additive, current-document scoped, and must not change native buffer contents, selection, caret, Quick Nav, braille, Say All, or structural speech.
- Tooltip behavior is intentionally unchanged. Tooltip timing is not exposed because the current speech routes cannot provide reliable full-token timing.
- `sequence_merger.py` was removed after a repository-wide dependency audit found no active source, test, packaging, or documentation dependency. Do not reintroduce sequence-merging behavior without a defined requirement and focused coverage.

## Documentation map

| Document | Role |
| --- | --- |
| `WEB-BUFFER-LOAD-RESEARCH.md` | Historical NVDA lifecycle research and the no-buffer-mutation boundary. |
| `plans/2026-07-20-web-summary-v0.md` | Historical manual Page Summary design. |
| `plans/2026-07-21-automatic-page-summary-v1.md` | Historical automatic Page Summary design. |
| `plans/2026-07-22-page-orientation-presentation-research.md` | Archived virtual-buffer presentation research; not implementable as an add-on. |
| `plans/2026-07-23-page-load-notifications-v1.md` | Historical Page Ready design. |
| `plans/2026-07-23-edge-notification-controls.md` | Historical Edge notification-controls design. |

When behavior changes, update this status document and the relevant user-facing documentation together. Historical plans should be retained for provenance, not duplicated as competing current roadmaps.
