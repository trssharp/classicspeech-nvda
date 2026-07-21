# Firefox Busy-State Taming Implementation Plan

> **For Hermes:** Execute only after explicit approval, task-by-task, with a source review after each task. This document is a plan, not an authorization to change ClassicSpeech or NVDA core.

**Goal:** Establish whether Firefox's repeated native page-load `busy` chatter is exclusively a redundant Gecko root-document Busy state transition, then—only if the evidence proves that strict predicate—propose and validate a disabled-by-default NVDA-core suppression that preserves all other accessibility feedback.

**Architecture:** Phase 1 is an observational ClassicSpeech GlobalPlugin probe. It reuses the existing ClassicSpeech diagnostic-logging preference and records provenance around `gainFocus`, `stateChange`, and `documentLoadComplete`; it neither changes the speech filter nor alters event dispatch, focus, caret, selection, or Page Summary. Phase 2 is conditional and belongs in NVDA core, not ClassicSpeech: a Firefox/Mozilla `Document.event_stateChange` override asks a Gecko virtual-buffer predicate whether a state delta is exactly root-focused Busy-only while loading. Only then may it update speech's state cache with `OutputReason.ONLYCACHE`, retain braille/vision updates, and omit that one redundant speech emission.

**Tech Stack:** ClassicSpeech Python GlobalPlugin/harnesses; installed-NVDA Firefox and Edge live harness; NVDA master at `C:\Users\trssh\Documents\development\nvda development\nvda master` (examined at `0e9ea2c2c`); NVDA config feature flags and unit tests.

---

## Non-negotiable product and safety contract

- Do not suppress or rewrite literal speech text (`busy`, `document`, a title, etc.) in `speech.extensions.filter_speechSequence`. At that hook, ClassicSpeech has no event/object/reason/backend provenance, so a string filter could remove legitimate focus, review, Say All, or a real non-load Busy update.
- Do not withhold or reorder `nextHandler()` from ClassicSpeech's GlobalPlugin events. It would risk NVDA virtual-buffer setup, Browse Mode focus/caret handling, native reporting, and Say All. The diagnostic handlers must call it exactly once, first, and then observe only.
- Phase 1 must add **no new user setting, no new config key, no UI control, no speech, no filtering, no focus/caret/selection mutation, and no browser-specific behavior change**. It is debug-gated by the existing ClassicSpeech `debugLogging` preference.
- The existing automatic Page Summary remains additive, count-only, and independently readiness-gated. Diagnostics must not alter its callback, retry, dedupe, manual `NVDA+Shift+U` command, or title-free output.
- A future core feature must default to disabled and be Firefox/Gecko-only. It must not affect Chromium/Edge, UIA, focus mode, a ready buffer, an unfocused object, a focus ancestor, or any state delta other than exactly Busy.
- Preserve the user’s access to meaningful loading/state information. This work may remove only proven duplicate **state-change** Busy chatter; it deliberately retains Busy information present in NVDA's initial focus report and retains real Busy changes outside the strict predicate.

## Source-backed conclusion and rationale

ClassicSpeech cannot safely solve this at the add-on speech boundary. Its filter receives final speech sequences without event provenance; its GlobalPlugin handlers must not suppress downstream native handling. NVDA master instead shows the relevant terminal behavior:

- Firefox read-only documents use `virtualBuffers.gecko_ia2.Gecko_ia2` through `source/NVDAObjects/IAccessible/mozilla.py`, `Document._get_treeInterceptorClass`.
- Normal `NVDAObject.event_stateChange` speaks changed states with `speech.speakObjectProperties(..., states=True, reason=OutputReason.CHANGE)` and then updates braille and vision (`source/NVDAObjects/__init__.py`, lines 1344–1359).
- `VirtualBuffer.isReady` means a buffer handle exists and `isLoading` is false (`source/virtualBuffers/__init__.py`, lines 553–557). Loading-period events are not reliably handled at the Gecko tree-interceptor layer, so the applicable Firefox-specific terminal seam is `NVDAObjects.IAccessible.mozilla.Document.event_stateChange`.
- Initial Browse Mode entry is separate: `BrowseModeDocumentTreeInterceptor.event_treeInterceptor_gainFocus` sets the initial caret, speaks the root document/title/states or starts Say All, and speaks the initial line (`source/browseMode.py`, lines 1835–1893). It is expressly out of scope.
- NVDA's `OutputReason.ONLYCACHE` updates `_speakObjectPropertiesCache` without generating speech (`source/speech/speech.py`, lines 769–775). It is the required cache-preservation mechanism if—and only if—the strict predicate later passes.

Therefore, ultimate suppression, if justified at all, must be a narrow **NVDA-core Firefox/Gecko-only `Document.event_stateChange` behavior**, gated by an experimental disabled-by-default feature flag. It is not a ClassicSpeech text-filter feature.

## Evidence gate: required decision rule

Proceed from Phase 1 to a core patch proposal only when each Firefox repeated utterance targeted for removal has logs proving all of the following for the same event:

1. Event name is `stateChange`, not `gainFocus`, `treeInterceptor_gainFocus`, `documentLoadComplete`, initial root focus output, Page Summary, initial caret output, or Say All.
2. The event object is the current focus object **and** the virtual buffer's `rootNVDAObject` by identity; it is not merely a focus ancestor.
3. The event is Gecko-backed: the focused tree interceptor is `virtualBuffers.gecko_ia2.Gecko_ia2` (or a verified subclass), and its root/event identity is stable.
4. The buffer is loading (`isLoading=True`, `isReady=False`) and in Browse Mode (`passThrough=False`).
5. A prior speech-state cache exists, and the symmetric difference of cached and current state sets is exactly `{controlTypes.State.BUSY}`.
6. Each candidate record correlates to one of the repeated observed native Busy utterances, while the automatic Page Summary remains separately count-only and once-per-ready-current-document.
7. Equivalent Edge/Chromium runs do not produce Gecko-qualified candidates and do not change behavior.

Any missing, unstable, ambiguous, or additional state is a failed gate—not a reason to broaden the predicate.

## Phase 1 — ClassicSpeech diagnostics only

### Task 1: Add a pure, defensive event snapshot formatter and failing harness coverage

**Objective:** Create a test-first, log-only representation of provenance needed to prove or reject the strict predicate, without making a behavior decision.

**Files:**
- Modify: `classicSpeech.py`
- Modify: `tests/classic_speech_web_summary_harness.py`
- Do not modify: `_speech_core/plugin_config.py`, `_speech_core/settings/advanced_config.py`, `_speech_core/settings/advanced_panel.py`, any speech processor, Page Summary configuration, or any NVDA source in this phase.

**Step 1: Add failing harness tests before production code**

Extend the existing fake-NVDA setup in `tests/classic_speech_web_summary_harness.py` with fake focus, focus-ancestor, tree-interceptor, root, state-cache, and event objects. Add tests that assert a structured diagnostic record has exactly these fields and that safe lookup failures are represented rather than raised:

```python
def test_busy_diagnostic_record_includes_required_event_focus_buffer_and_state_fields(): ...
def test_busy_diagnostic_marks_root_focused_gecko_loading_busy_only_candidate(): ...
def test_busy_diagnostic_marks_focus_ancestor_and_busy_plus_other_delta_non_candidates(): ...
def test_busy_diagnostic_does_not_call_speech_filter_or_mutate_focus_caret_selection_or_cache(): ...
def test_busy_diagnostic_is_silent_when_classicspeech_debug_logging_is_off(): ...
```

**Required record fields (one stable, single-line structured `ClassicSpeech debug:` record per observed event):**

- `t_monotonic`: `time.monotonic()` captured at observation; no wall-clock inference.
- `event`: exactly `gainFocus`, `stateChange`, or `documentLoadComplete`.
- Object identity and provenance: `obj_id`, fully qualified `obj_class`, `app_name`, `app_module_class`, `role`, safe `name`, `states` (stable enum names), and `busy_now`.
- Focus relationship: `focus_id`, `is_focus`, `focus_ancestor_ids`, `is_focus_ancestor`, `focus_difference_level` if safely available.
- Tree-interceptor/buffer identity: `tree_interceptor_id`, qualified `tree_interceptor_class`, `backend` (`gecko`, `chromium`, or `none/other`), `root_id`, `is_root`, `vbuf_handle_id`, `is_loading`, `is_ready`, and `pass_through`.
- State provenance: `cached_states_present`, `cached_states`, `current_states`, `state_symmetric_difference`, `busy_only_delta`, and `strict_candidate`.
- Correlation context: `automatic_summary_pending` and `automatic_summary_reported` as opaque identity/boolean status only; never log page text, document content, credentials, URLs, or other sensitive content.

Normalize enum/state output deterministically (for example, sorted state names), use safe placeholders for unavailable/dead objects, and do not retain object references beyond the synchronous record construction.

**Step 2: Run the focused harness and verify it fails for the missing formatter**

```sh
python tests/classic_speech_web_summary_harness.py
```

Expected: failure naming the missing diagnostic helper/record fields, while existing Page Summary tests remain unchanged.

**Step 3: Implement only defensive observation helpers**

- Add private helpers adjacent to the existing automatic-summary event helpers, for example `_busy_diagnostic_snapshot(event_name, obj)` and `_log_busy_diagnostic(event_name, obj)`.
- Import only what is needed for snapshotting (`time` and existing NVDA APIs); do not register a new extension point, alter `_filterSpeechSequence`, or import/control speech output.
- Read `_speakObjectPropertiesCache.get("states")` without updating it. The log is diagnostic evidence, not cache repair.
- Treat a state change as a *candidate label* only when the exact evidence-gate predicate is true; never branch behavior on that label.

**Step 4: Re-run the focused harness**

```sh
python tests/classic_speech_web_summary_harness.py
python -m py_compile classicSpeech.py tests/classic_speech_web_summary_harness.py
```

Expected: PASS. The test doubles prove no calls to `ui.message`, no speech-filter registration/mutation, no `wx.CallLater` change, no `nextHandler` suppression, and no focus/caret/cache mutation from the diagnostic helper.

### Task 2: Observe the three native event types without changing their behavior

**Objective:** Route the evidence collection through the actual ClassicSpeech GlobalPlugin event boundary while preserving native NVDA event handling exactly.

**Files:**
- Modify: `classicSpeech.py`
- Modify: `tests/classic_speech_web_summary_harness.py`

**Step 1: Add failing dispatch-order and no-side-effect tests**

```python
def test_busy_diagnostic_gain_focus_calls_next_handler_once_before_logging(): ...
def test_busy_diagnostic_state_change_calls_next_handler_once_before_logging(): ...
def test_busy_diagnostic_document_load_complete_calls_next_handler_once_before_logging(): ...
def test_busy_diagnostic_does_not_change_automatic_page_summary_scheduling_or_deduplication(): ...
def test_busy_diagnostic_off_leaves_all_three_events_observationally_inert(): ...
```

The `stateChange` test must cover both a root-focused Gecko Busy-only fake and a non-root/focus-ancestor fake. It must prove that both delegate normally and differ only in the logged candidate classification.

**Step 2: Run the focused harness and verify failure**

```sh
python tests/classic_speech_web_summary_harness.py
```

Expected: failure because the corresponding observer handlers do not yet exist.

**Step 3: Implement the minimal handlers**

- Extend `event_gainFocus` and `event_documentLoadComplete` only by calling the log helper after their existing `nextHandler()` calls; retain their current automatic-summary logic and ordering unchanged.
- Add `event_stateChange(self, obj, nextHandler)` that calls `nextHandler()` exactly once, first, then invokes the log helper.
- Invoke the helper only when `get_debug_logging_enabled()` is true. Debug off must produce no inspection-sensitive work beyond the ordinary existing event path.
- Catch diagnostic lookup/logging exceptions and emit at most an existing debug-safe failure record. Never let diagnostics interrupt native handling.
- Do not create a configuration setting or a UI checkbox: the existing Advanced-panel “Enable ClassicSpeech diagnostic logging” is the only gate.

**Step 4: Re-run regression checks**

```sh
python tests/classic_speech_web_summary_harness.py
python tests/classic_speech_core_harness.py
python -m compileall -q _speech_core tests classicSpeech.py
```

Expected: PASS. The source/harness review must show no change to `_filterSpeechSequence`, its registration, automatic-summary settings, or `ui.message` paths.

### Task 3: Perform the live Firefox/Edge evidence matrix

**Objective:** Determine, from logs and observed speech, whether repeated Firefox chatter satisfies the exact Busy-only predicate and whether all protected behavior remains unchanged.

**Files:**
- Runtime scratchpad and NVDA log only after the preceding source gate and explicit deployment approval.
- Create after each run: a date-stamped redacted evidence note under `docs/research/` or the user-approved evidence location. Do not place raw logs, URLs, page content, or personal data in the repository.

**Preconditions:**

1. Confirm the running NVDA version, config path, scratchpad add-on path, browser versions, and log path.
2. Deploy the verified diagnostics-only source with a timestamped scratchpad backup; compile it and compare source/runtime trees.
3. Restart NVDA; prove from the log that ClassicSpeech loaded and that diagnostics are enabled through the existing Advanced setting.
4. Leave ClassicSpeech automatic Page Summary configured exactly as the user normally tests it; record whether its opt-in is enabled. Test Page Summary separately rather than treating it as the source of native Busy speech.
5. Use a reproducible non-sensitive public test page or a local test fixture. Record an opaque page label, not a full URL/content dump.

**Matrix (12 core runs):**

For each browser—Firefox, then Edge/Chromium—run each action with NVDA's **Automatic Say All on page load** both Off and On:

1. New tab / initial navigation to the fixture.
2. Reload the already-loaded fixture.
3. Start a deliberately slow loading navigation, then navigate away before the first load settles (or activate a second navigation while the first remains loading).

For every run, capture:

- browser, action, Say All setting, automatic Page Summary setting, page label, and run start/end monotonic times;
- observed spoken sequence in order, marking repeated Busy utterances without paraphrasing root/title/caret output;
- matching diagnostic records for `gainFocus`, `stateChange`, and `documentLoadComplete`;
- candidate count and all `strict_candidate=True` records;
- focus/root/buffer identities and `isLoading`/`isReady`/`passThrough` transitions;
- verification that the automatic summary (if enabled) occurs once only after the current document is ready and remains count-only;
- before/after focus object identity, Browse Mode caret/review position, and whether Say All began/continued as native NVDA configured it.

**Pass threshold for advancing:** Firefox repeats are consistently represented by one or more `strict_candidate=True` state-change records, with stable root/focus/buffer identity and an exactly Busy symmetric difference, while all Edge candidates are false and protected behavior is unchanged. The resulting redacted note must list the records that support each predicate clause.

**Stop conditions — stop, preserve native behavior, and report rather than implement a core patch if any occur:**

- Repeated speech is from `gainFocus`, initial root/title reporting, initial caret, `documentLoadComplete`, Page Summary, or Say All rather than state change.
- The event object is a focus ancestor, a descendant, a different root, or any non-current object.
- The current buffer is ready, in focus mode, non-Gecko, missing/unstable, or not the event object's root.
- The cache is absent or the delta is empty, unknown, Busy-plus-any-other-state, or any non-Busy state.
- Edge/Chromium produces a candidate, the candidate occurs in non-browser content, or Firefox evidence is not repeatable.
- Diagnostics change speech timing/content, focus, caret, selection, Page Summary count/timing/deduplication, or Say All behavior.
- Native Busy feedback proves meaningful rather than redundant in the tested loading path.

**Step 4: Remove or park diagnostics after decision**

If the gate fails, remove the temporary probe in a separate tested change (or keep it only with explicit user approval for future data collection), retain the redacted conclusion, and make no suppression change. If the gate passes, freeze the evidence note and start Phase 2 in an NVDA-core branch; do not expand ClassicSpeech behavior.

## Phase 2 — conditional NVDA-core feature (only after Phase 1 passes)

### Task 4: Add failing NVDA-core tests for the predicate and cache-preserving behavior

**Objective:** Prove the disabled default delegates completely and the enabled feature suppresses only a root-focused Gecko Busy-only loading delta.

**Files:**
- Create: `tests/unit/test_geckoBusyStateChange.py`
- Modify if a reusable fake/fixture is demonstrably needed: `tests/unit/objectProvider.py`
- Do not alter tests for Browse Mode initial-focus/Say All behavior except to add focused regression coverage when a suitable existing system/unit seam is identified.

**Step 1: Write failing tests first**

Use small fakes for the Mozilla document, focus object, Gecko virtual buffer, speech cache, speech call, braille handler, and vision handler. Test the actual terminal method or a narrowly extracted predicate, not a text string.

Required cases:

1. Default `BoolFlag` behavior delegates to the existing base `event_stateChange`: normal speech, braille, and vision behavior remain intact.
2. Explicitly enabled + Gecko root/current focus + `isLoading=True` + `isReady=False` + `passThrough=False` + prior cached states + symmetric delta exactly `{BUSY}`: no changed-state speech; cache updates to current states using `OutputReason.ONLYCACHE`; braille and vision still update once.
3. Missing state cache delegates.
4. Busy plus any other changed state delegates.
5. A non-Busy-only change delegates.
6. Non-root object, focus ancestor, and non-current-focus object delegate.
7. Ready buffer, focus mode, non-Gecko interceptor, Chromium/Edge-style buffer, and no buffer delegate.
8. The predicate never changes title/name output, never calls Browse Mode focus logic, and never starts/stops Say All.

**Step 2: Run the focused unit target and verify failure**

```sh
./rununittests.bat -k test_geckoBusyStateChange
```

Expected: FAIL because the feature flag, predicate, and Mozilla override do not exist.

### Task 5: Add an experimental disabled-by-default feature flag and accessible Advanced Settings control

**Objective:** Make the proposed NVDA behavior explicitly opt-in/out/testable without creating a stable Browse Mode setting.

**Files:**
- Modify: `source/config/configSpec.py`
- Modify: `source/gui/settingsDialogs.py` (the `AdvancedSettingsPanel`, in a clearly named Virtual Buffers group)
- Modify: `source/documentation/userGuide/en/userGuide.md` and its translation/source counterparts only after confirming the current documentation layout and build process
- Modify/Create: the focused config/UI tests located through NVDA's current test conventions

**Implementation contract:**

- Add under `[virtualBuffers]`:

```ini
suppressGeckoBusyStateChangesDuringLoad = featureFlag(optionsEnum="BoolFlag", behaviorOfDefault="disabled")
```

- Expose it through `gui.nvdaControls.FeatureFlagCombo` in **Advanced Settings > Virtual Buffers**, with `keyPath=["virtualBuffers", "suppressGeckoBusyStateChangesDuringLoad"]` and the standard Default / Enabled / Disabled semantics.
- Use an accessible, explicit label explaining its narrow scope, for example: `Suppress Firefox Busy state changes while a page is loading:`. Do not imply it suppresses document titles, loading generally, or browser page-load speech.
- Follow `projectDocs/dev/featureFlags.md` and `projectDocs/dev/userGuideStandards.md`: Default must resolve disabled, while users can explicitly choose Enabled or Disabled.
- Add translatable-string comments and the user-guide feature-setting entry only after the exact string and anchor are reviewed.

**Step 1: Run focused config/UI tests, then implement minimally until they pass.**

**Step 2: Run translatable-string checks after adding user-facing text.**

```sh
./runcheckpot.bat
```

Expected: PASS.

### Task 6: Implement the fail-closed Firefox-only terminal seam

**Objective:** Suppress only the proven redundant Busy state-change speech while retaining cache, braille, vision, and every unrelated native flow.

**Files:**
- Modify: `source/NVDAObjects/IAccessible/mozilla.py`
- Modify: `source/virtualBuffers/gecko_ia2.py`
- Modify: `tests/unit/test_geckoBusyStateChange.py`

**Step 1: Add a narrowly named Gecko-buffer predicate**

Add a method on `Gecko_ia2`, for example `shouldSuppressRootBusyStateChangeDuringLoad(obj)`, that returns `True` only when every condition holds:

1. `config.conf["virtualBuffers"]["suppressGeckoBusyStateChangesDuringLoad"]` resolves true.
2. This interceptor is the focused document's Gecko buffer; `obj is self.rootNVDAObject`; `obj is api.getFocusObject()`.
3. `self.isLoading is True`, `self.isReady is False`, and `self.passThrough is False`.
4. `obj._speakObjectPropertiesCache` contains a prior `"states"` value.
5. The symmetric difference of that cached state set and `obj.states` is exactly `{controlTypes.State.BUSY}`.

All exceptions, missing attributes, and uncertainty return `False` (delegate natively).

**Step 2: Override only `mozilla.Document.event_stateChange`**

- Obtain the current tree interceptor and ask the predicate; do not hook generic `NVDAObject.event_stateChange`, Chromium, event dispatch, or Browse Mode focus handlers.
- On false, call `super().event_stateChange()` unchanged.
- On true, call `speech.speakObjectProperties(self, states=True, reason=OutputReason.ONLYCACHE)` to update the state cache without speech, then call the same braille and vision updates the base method would make.
- Do not call `nextHandler` from this terminal NVDAObject event method; this is not a GlobalPlugin wrapper. Do not alter `event_treeInterceptor_gainFocus`, `event_gainFocus`, document load handling, title/name properties, caret placement, or Say All.

**Step 3: Re-run every focused predicate/behavior test after each minimal change**

```sh
./rununittests.bat -k test_geckoBusyStateChange
```

Expected: PASS only when all false branches preserve the native base behavior and the sole true branch preserves cache/braille/vision.

### Task 7: Core quality gate and controlled live verification

**Objective:** Prove the experimental feature is constrained and user-understandable before any proposal/upstream submission.

**Files:** No intended production changes.

**Automated gate:**

```sh
./rununittests.bat -k test_geckoBusyStateChange
./runlint.bat
./runcheckpot.bat
uv run prek run --files source/NVDAObjects/IAccessible/mozilla.py source/virtualBuffers/gecko_ia2.py source/config/configSpec.py source/gui/settingsDialogs.py tests/unit/test_geckoBusyStateChange.py
```

Run the full NVDA unit suite when practical before presenting the feature for review. Record any unavailable gate honestly; do not replace it with presumed passing results.

**Live matrix:** Repeat the Phase 1 12-run Firefox/Edge matrix with the flag in Default, Enabled, and Disabled states. The expected comparison is:

- Default and explicit Disabled: byte-for-byte equivalent event provenance and native behavior to the pre-feature baseline; Firefox chatter remains native.
- Enabled Firefox: only the logged/state-proven root-focused Gecko Busy-only loading state-change utterances disappear; initial title/root focus, initial caret line, manual Page Summary, automatic count-only Page Summary, focus, browse cursor, and configured Say All remain unchanged.
- Enabled Edge/Chromium: no behavior difference and no Gecko predicate call that returns true.
- Real non-load Busy changes, Busy-plus-other-state changes, ready-buffer changes, and focus-mode changes: remain spoken normally.

**Final review checklist:**

- No ClassicSpeech speech-filter change and no ClassicSpeech event suppression.
- No change to title behavior (the approved Title removal at `3f672ba` remains intact).
- No change to initial caret, review/caret selection, Browse Mode focus entry, or Say All.
- No Chromium/Edge, UIA, or non-Gecko behavior change.
- No loss of a non-load or compound state change.
- Flag is experimental, explicitly documented, default-disabled, and discoverable in Advanced Settings.
- User-facing wording states the exact Firefox/loading limitation and preserves accessibility clarity rather than suggesting loading feedback is globally unimportant.

## Rollback and decision checkpoints

- **After Task 3:** If evidence fails the strict predicate, ship no suppression. Restore/remove diagnostics unless the user explicitly keeps them for future data collection.
- **After Task 6:** Any unexpected title, initial-caret, Say All, braille, vision, Edge, or real-state regression means disable/remove the core feature and return to evidence collection; do not loosen the predicate.
- **Before any submission:** keep the ClassicSpeech branch and NVDA-core branch separate. This plan authorizes no commit, deployment, or upstream change by itself.

## Known risks and mitigations

- **Misidentifying focus speech as state-change chatter:** log all three relevant event types, correlate them to observed speech, and stop unless the event is `stateChange`.
- **Missing changed-state payload from the Windows event:** derive only a symmetric difference from NVDA's prior speech cache and current state set; cache absence fails closed.
- **Breaking state reporting after suppression:** use `ONLYCACHE` and retain braille/vision updates; test them explicitly.
- **Overbroad browser suppression:** keep the predicate on Gecko only and explicitly exercise Edge/Chromium.
- **Destroying initial page orientation:** leave `BrowseModeDocumentTreeInterceptor.event_treeInterceptor_gainFocus` completely untouched and test title, caret, and Say All separately.
- **Diagnostic privacy/noise:** debug-gate the probe, omit URLs/content, use opaque IDs/state names, and remove/park the probe promptly after the decision.
