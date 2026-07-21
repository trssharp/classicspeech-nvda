# Automatic Page Summary v1 Implementation Plan

> **For Hermes:** Use `subagent-driven-development` to implement this plan task-by-task with a fresh review after each task.

**Goal:** Add an accessible, opt-in automatic Page Summary that speaks once for each newly loaded, ready Browse Mode document without changing normal browser speech, focus, review position, or the manual command.

**Architecture:** Continue to count only NVDA's active Browse Mode virtual buffer through the existing pure `build_summary` model. A small GlobalPlugin integration observes NVDA's `documentLoadComplete` event, then waits for the *same* focused tree interceptor to report `isReady` before speaking one native `ui.message`. The readiness predicate, not a fixed browser delay, determines whether a summary may be spoken. A short bounded retry only bridges the normal delay between the document-load event and virtual-buffer readiness.

**Tech Stack:** Python 3.11, NVDA GlobalPlugin/event APIs, NVDA virtual buffers, wx `CallLater`, existing ClassicSpeech harnesses.

---

## Product contract

- The feature is disabled by default.
- A new native checkbox lives in the existing **Page Summary** category:
  `Automatically report summary when a Browse Mode page is ready`.
- The manual `NVDA+Shift+U` command stays unchanged and works whether automatic reporting is on or off.
- Automatic reporting is limited to the current, focused Browse Mode tree interceptor.
- It speaks once per document-load cycle only after `document.isReady` is true.
- It uses existing Page Summary selected types and wording, including `No selected element types found.`
- It never calls `QuickNavItem.report()` or `moveTo()` and never moves focus, system caret, browse cursor, selection, or document mode.
- It must not change normal page-load speech, Say All, browser semantics, or ClassicSpeech's speech filter.
- If the focus/document changes before readiness, the pending report is silently discarded.
- A browser-specific count difference is valid because Firefox and Chromium build separate NVDA virtual-buffer backends. The feature must never normalize or compare counts across browsers.

## NVDA API facts this plan relies on

- NVDA dispatches `event_documentLoadComplete` to GlobalPlugins before app and tree-interceptor handlers (`source/eventHandler.py`).
- `VirtualBuffer.isReady` is true only when NVDA has a valid buffer handle and it is no longer loading (`source/virtualBuffers/__init__.py`).
- A Chromium buffer can initially be empty; NVDA explicitly waits for a later `documentLoadComplete` opportunity rather than assuming a first focus event was ready.
- Therefore, `documentLoadComplete` is the wake-up event, while `isReady` plus same-document identity is the permission to speak.

## Task 1: Add persistent opt-in configuration

**Objective:** Store the automatic-reporting setting with a safe disabled default.

**Files:**
- Modify: `_speech_core/plugin_config.py`
- Modify: `_speech_core/settings/web_summary_config.py`
- Test: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing tests**

Add tests proving:

```python
def test_page_summary_auto_reporting_defaults_to_off(): ...
def test_page_summary_auto_reporting_round_trips_true_and_false(): ...
def test_page_summary_auto_reporting_coerces_invalid_saved_values_to_off(): ...
```

**Step 2: Run the focused harness**

```bash
python tests/classic_speech_web_summary_harness.py
```

Expected: FAIL because no automatic-reporting helper exists.

**Step 3: Implement minimal config helpers**

- Add `automaticReportOnPageLoad` as a boolean defaulting to `False` in `pageSummaryData`.
- Add `get_automatic_reporting_enabled()` and `set_automatic_reporting_enabled(enabled)`.
- Treat missing or invalid data as disabled; never turn a feature on from malformed configuration.

**Step 4: Re-run focused harness**

Expected: PASS.

**Step 5: Commit**

```bash
git add _speech_core/plugin_config.py _speech_core/settings/web_summary_config.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: add automatic page summary setting"
```

## Task 2: Add the accessible Page Summary checkbox

**Objective:** Let users enable or disable automatic reports through the existing transaction-safe dialog.

**Files:**
- Modify: `_speech_core/settings/web_settings_dialog.py`
- Test: `tests/classic_speech_web_settings_harness.py`

**Step 1: Write failing behavioral tests**

Cover:

```python
def test_page_summary_panel_has_named_auto_report_checkbox(): ...
def test_auto_report_checkbox_uses_saved_setting(): ...
def test_auto_report_checkbox_marks_apply_visible_and_persists(): ...
def test_auto_report_apply_then_cancel_restores_applied_checkbox_value(): ...
```

**Step 2: Run the settings harness**

```bash
python tests/classic_speech_web_settings_harness.py
```

Expected: FAIL because the checkbox and transaction snapshot are absent.

**Step 3: Implement the checkbox**

- Place it before the existing checklist in the Page Summary panel.
- Use `wx.CheckBox` and the label exactly as specified above.
- Bind `wx.EVT_CHECKBOX` to the existing dirty/apply handler.
- Include its state in initial snapshot, Apply baseline refresh, and Cancel/close restoration.
- Preserve the Page Summary checklist's native `EVT_CHECKLISTBOX` handling unchanged.

**Step 4: Re-run settings and summary harnesses**

Expected: PASS.

**Step 5: Commit**

```bash
git add _speech_core/settings/web_settings_dialog.py tests/classic_speech_web_settings_harness.py
git commit -m "feat: add automatic page summary checkbox"
```

## Task 3: Build a narrow ready-document reporter

**Objective:** Isolate scheduling, readiness validation, and once-per-document suppression from the manual summary command.

**Files:**
- Modify: `classicSpeech.py`
- Test: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing integration tests with fake documents**

Cover:

```python
def test_document_load_does_nothing_when_auto_reporting_is_off(): ...
def test_ready_current_document_speaks_one_existing_summary(): ...
def test_loading_document_is_rechecked_without_speaking_early(): ...
def test_pending_report_is_discarded_when_focus_changes_document(): ...
def test_repeated_document_load_events_speak_once_per_document_cycle(): ...
def test_auto_report_uses_native_message_without_moving_items_or_focus(): ...
def test_plugin_termination_cancels_pending_auto_report_callbacks(): ...
```

The fake document must expose `_iterNodesByType`, `isReady`, and a stable object identity. Stub `wx.CallLater`/callback scheduling so tests do not wait in real time.

**Step 2: Run focused harness**

```bash
python tests/classic_speech_web_summary_harness.py
```

Expected: FAIL because the document-load integration does not exist.

**Step 3: Implement a dedicated private integration boundary**

Add narrowly named helpers on `GlobalPlugin`, for example:

```python
def event_documentLoadComplete(self, obj, nextHandler): ...
def _schedule_automatic_page_summary(self, document): ...
def _report_automatic_page_summary_if_ready(self, document, attempt): ...
```

Required behavior:

1. Call `nextHandler()` first so NVDA keeps its native page-load flow.
2. Exit unless the opt-in setting is enabled.
3. Obtain the focused object's `treeInterceptor`; exit unless it is the document associated with this event and supports `_iterNodesByType`.
4. Mark the document-load cycle pending before scheduling, so duplicate events cannot queue duplicate speech.
5. On callback, re-read focus and require identity equality with the original document.
6. Require `document.isReady is True` before calling `build_summary` and one native `ui.message`.
7. If not ready, schedule a bounded retry. The retry is a wait mechanism only; it never speaks unless the readiness predicate passes.
8. Drop the pending state on success, stale focus, feature disablement, termination, or retry exhaustion.
9. Track reported document-load cycles without retaining stale document objects after termination.

Use `wx.CallLater` or the existing NVDA event queue only for deferred execution; do not add browser-specific Gecko/UIA branches, browser DOM inspection, arbitrary fixed “page loaded” sleeps, or speech-filter hooks.

**Step 4: Run focused harness**

Expected: PASS.

**Step 5: Commit**

```bash
git add classicSpeech.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: report ready page summaries automatically"
```

## Task 4: Source gate and independent review

**Objective:** Prove the automatic path is opt-in, buffer-ready-gated, and regression-safe.

**Files:** No intended production changes.

**Step 1: Run all isolated harnesses and compilation**

```bash
python -m compileall -q _speech_core tests classicSpeech.py
for test in tests/*harness.py; do python "$test"; done
git diff --check main...HEAD
```

Expected: all commands pass.

**Step 2: Review the complete branch**

Inspect `main...HEAD` for:

- disabled default;
- no automatic speech filter changes;
- no focus/cursor/QuickNav movement;
- no browser backend branches;
- same-document and ready-state guards;
- no unbounded callback retention;
- accessible checkbox and transaction coverage.

**Step 3: Commit the plan document if still uncommitted**

```bash
git add docs/plans/2026-07-21-automatic-page-summary-v1.md
git commit -m "docs: plan automatic page summary"
```

## Task 5: Scratchpad deployment and live NVDA validation

**Objective:** Validate real user-visible behavior in installed NVDA after approval.

**Files:** Runtime scratchpad only after source gate and explicit approval.

**Step 1: Make timestamped backup and deploy whole runtime plugin tree**

- Back up `C:\Users\trssh\AppData\Roaming\nvda\scratchpad\globalPlugins`.
- Copy `classicSpeech.py` and `_speech_core` from this feature branch.
- Remove `__pycache__`.
- Compile scratchpad files and compare source/runtime hashes.

**Step 2: Restart installed NVDA and inspect its log**

Confirm the scratchpad plugin loads without traceback and the automatic setting is available in:

```text
NVDA menu > Preferences > ClassicSpeech > Web / Browse Mode Settings > Page Summary
```

**Step 3: Live matrix in Firefox and Edge**

For each browser, verify:

1. Default disabled: opening a page does not auto-speak a summary.
2. Enabled: a newly loaded page speaks exactly one summary after the document is ready.
3. Manual `NVDA+Shift+U` remains available and does not suppress automatic reporting on a later new page.
4. Reloading a page creates one new automatic summary, not duplicates.
5. Navigation away before completion does not speak an old-page summary.
6. A dynamic page does not speak before its buffer is ready.
7. Before/after checks prove focus and browse cursor are unchanged.
8. Browser-specific count differences, if any, are recorded as buffer semantics rather than treated as a defect.

**Step 4: Record results and only then mark complete**

Report exact pages, browser, NVDA log evidence, observed speech, and any remaining timing limitation.

## Risks and mitigations

- **Document-load event before ready buffer:** gate on `isReady` and re-check identity.
- **Chromium empty early buffer:** do not speak at a load event alone; retry only while current document remains pending.
- **Duplicate browser events:** suppress pending/reported cycles per document object.
- **Navigation race:** compare the currently focused tree interceptor at callback time.
- **Interrupting native load speech:** call `nextHandler()` first and defer the optional message to a later event-loop turn.
- **Memory leak from delayed callbacks:** cancel/clear callbacks in `terminate()` and use bounded retries.
- **User surprise:** disabled default plus clear native checkbox.
