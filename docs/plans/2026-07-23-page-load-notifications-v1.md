# Page Ready Notification v1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add one default-off, user-configurable Browse Mode notification when the current focused virtual buffer becomes ready.

**Architecture:** Extend the existing Page Summary configuration and `WebBrowseSettingsDialog`. Reuse the existing document-identity/readiness lifecycle in `GlobalPlugin`. Do not inspect browser DOM/ARIA trees, mutate virtual-buffer content, change focus/caret/selection, or add browser-backend branches.

**Deferred:** NVDA exposes no safe public global-plugin event that proves a page has started loading. A Loading notification is therefore deferred; do not approximate one from focus events, `documentLoadComplete`, retries, or timers.

---

## Product contract

Persist below `classicSpeech.pageSummaryData`:

- `notifyWhenPageReady`: Boolean, default `False`.
- `pageReadyMessage`: String, default `Page ready`.

The message getter trims whitespace and returns the default for absent, non-string, or blank values. The setter does not alter the enable preference.

Before `Page-load summary:` in the Page Summary panel, add:

```text
Notify when page is ready
  Page ready message: [Page ready]
```

The complete label/edit row is hidden while its checkbox is unchecked. It must not be merely disabled: hiding keeps it out of tab order and prevents NVDA from reporting an unavailable edit field. Toggle handling must re-layout and refresh the scrolled Page Summary panel and preserve Apply, OK, Cancel, and Close transactions.

Runtime requirements:

1. Call `nextHandler()` before ClassicSpeech handling.
2. Require the current focus object's exact Browse Mode tree interceptor and callable `_iterNodesByType`.
3. Require `document.isReady is True`; deferred callbacks/retries are wake-ups only.
4. Emit one native `ui.message` per ready `VBufHandle` cycle when the option remains enabled.
5. Discard stale work when focus/document/cycle changes, the option is disabled, retry expires, or the plugin terminates.
6. When a configured automatic summary also occurs, emit Ready first and prove both outputs are retained.

## Tasks

### Task 1: Ready-only configuration

- Remove the now-deferred Loading settings/tests from the preliminary configuration change.
- Keep only Ready constants, helpers, strict boolean parsing, default fallback, and focused config coverage.

### Task 2: Accessible dependent Page Summary controls

- Modify `_speech_core/settings/web_settings_dialog.py`.
- Modify `tests/classic_speech_web_settings_harness.py`.
- Add a native checkbox plus a full hidden/shown label/edit row before Page-load summary.
- Prove visibility, live Apply, Apply baseline, Cancel/Close restoration, and source placement.

### Task 3: Ready lifecycle and tests

- Modify `classicSpeech.py` and `tests/classic_speech_web_summary_harness.py`.
- Reuse current focused-document and `VBufHandle` lifecycle state without tying Ready to a Page Summary mode.
- Cover disabled behavior, ready once-only delivery, summary ordering, stale document/cycle cancellation, setting disablement after scheduling, and termination.

### Task 4: Full gate

- Run focused harnesses, all `tests/*harness.py`, compilation, and `git diff --check`.
- Obtain separate spec-compliance and quality reviews.
- Commit only after approval. Do not deploy/restart NVDA; Firefox and Chromium live testing remain required before merge or release.
