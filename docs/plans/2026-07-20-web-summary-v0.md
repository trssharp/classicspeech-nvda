# Web Summary v0 Implementation Plan

> **For Hermes:** Implement this plan task-by-task on the local `feat/web-summary-v0` branch. Do not push, deploy to scratchpad, or merge without Tim's approval after review and verification.

**Goal:** Add an on-demand ClassicSpeech Web Summary command on `NVDA+Shift+U` that reports counts for user-selected Browse Mode quick-navigation element types without moving focus or the browse cursor.

**Architecture:** Keep the feature separate from normal speech filtering and page-load handling. A small Web Summary model owns canonical NVDA quick-navigation item definitions, configuration, count collection, and final phrase formatting. The existing Web / Browse Mode Settings dialog gains a Page Summary category containing an accessible checklist of inclusion choices.

**Tech Stack:** Python 3.11, NVDA global-plugin APIs, NVDA Browse Mode virtual buffers, wxPython / `nvdaControls.CustomCheckListBox`, existing ClassicSpeech outside-NVDA harnesses.

---

## Confirmed NVDA quick-navigation choices

Each quick-navigation key moves forward; `Shift` plus the same key moves backward. These source-verified item types must appear in the Page Summary options list:

| Key | NVDA item type | Display label |
| --- | --- | --- |
| A | `annotation` | Annotations |
| B | `button` | Buttons |
| C | `comboBox` | Combo boxes |
| D | `landmark` | Landmarks |
| E | `edit` | Edit fields |
| F | `formField` | Form fields |
| G | `graphic` | Graphics |
| H | `heading` | Headings |
| K | `link` | Links |
| L | `list` | Lists |
| M | `frame` | Frames |
| O | `embeddedObject` | Embedded objects |
| Q | `blockQuote` | Block quotes |
| R | `radioButton` | Radio buttons |
| S | `separator` | Separators |
| T | `table` | Tables |
| W | `error` | Errors |
| X | `checkBox` | Check boxes |

Do not include `notLinkBlock` (`N`) in v0 because it is a navigation skip operation, not a countable element type. Defer overlapping link subsets (`U` unvisited links and `V` visited links), paragraph navigation, heading levels, and other optional NVDA types until the base summary is proven in live browsers.

## Product contract

### Command

- Gesture: `NVDA+Shift+U`.
- It is available only when an active browse-mode tree interceptor can supply supported quick-navigation iterators.
- If the current focus is not a supported browse-mode document, say one concise native-voice error such as `Page summary is not available here.`
- It must not change focus, selection, caret position, browse cursor position, mode, or normal page speech.

### Spoken output

- Count only selected item types.
- Omit every selected category whose count is zero.
- Do not add a redundant `Page summary` prefix to ordinary output.
- Use singular and plural naturally.
- Example: `2 landmarks, 42 links, 1 table.`
- If no selected type occurs in the current document, say: `No selected element types found.`
- Do not include page-load, ready, title, URL, or automatic announcements in v0.

### Settings

- Add a `Page Summary` category to the existing ClassicSpeech Web / Browse Mode Settings dialog.
- Explain: `Choose the Browse Mode element types included when you press NVDA+Shift+U. Checked items are included.`
- Use `nvdaControls.CustomCheckListBox`, not raw `wx.CheckListBox`.
- Each accessible row contains only the element label and its native checkbox state. Checked means on/included; unchecked means off/excluded. The quick-navigation key mapping remains documented in the canonical choices table above.
- Initial checked defaults: Headings, Landmarks, Links, Form fields, Buttons, and Tables.
- The checklist must honor the dialog's existing Apply / OK / Cancel transaction behavior.
- Do not expose an automatic-reporting checkbox until the page-ready lifecycle is separately designed, implemented, and proven. A no-op or future-only checkbox is not acceptable.

## Non-goals

- No automatic reporting during page load or refresh.
- No suppression, flushing, filtering, or replacement of NVDA browser speech.
- No browser-specific busy-state handling.
- No changes to existing native Browse Mode or Web Element Reporting settings.
- No mutation of the current virtual-buffer position or focus.
- No Voice Profile routing change; v0 uses the native NVDA speech path.

## Task 1: Add a focused, testable summary model

**Objective:** Define the supported item registry, defaults, inclusion normalization, counting contract, and phrase formatting outside the dialog and plugin.

**Files:**
- Create: `_speech_core/web_summary.py`
- Create: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing tests**

Cover at least:

```python
def test_requested_nvda_quick_nav_keys_are_exposed_in_stable_order(): ...
def test_default_included_types_are_headings_landmarks_links_forms_buttons_and_tables(): ...
def test_unknown_or_duplicate_saved_types_are_normalized_safely(): ...
def test_zero_counts_are_omitted_from_the_summary(): ...
def test_no_matching_selected_types_uses_the_explicit_empty_message(): ...
def test_summary_uses_natural_singular_and_plural_phrases(): ...
def test_counting_does_not_move_the_fake_document_cursor_or_focus(): ...
```

Use a fake document that records `iterNodesByType` calls and returns iterable fake items. Do not require a live browser for model tests.

**Step 2: Run the new harness**

```bash
python tests/classic_speech_web_summary_harness.py
```

Expected before implementation: failure because the module does not exist.

**Step 3: Implement the minimum model**

- Define canonical item records containing `itemType`, singular label, plural label, and forward quick-navigation key.
- Normalize persisted choices against that canonical registry.
- Count by consuming the document iterator without invoking any item report or move method.
- Catch `NotImplementedError` per type and treat that type as unavailable/zero for that document.
- Return plain data and a plain final string; do not speak from the model.

**Step 4: Run the focused harness**

Expected: all Web Summary model tests pass.

**Step 5: Commit**

```bash
git add _speech_core/web_summary.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: add web summary model"
```

## Task 2: Add persisted configuration and safe helpers

**Objective:** Store selected Page Summary types in ClassicSpeech configuration with safe defaults and validation.

**Files:**
- Modify: `_speech_core/plugin_config.py`
- Create: `_speech_core/settings/web_summary_config.py`
- Modify: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing configuration tests**

Verify:

```python
def test_page_summary_defaults_are_registered_in_classic_speech_config(): ...
def test_saved_choices_round_trip_in_stable_registry_order(): ...
def test_invalid_saved_choices_are_dropped_without_losing_valid_choices(): ...
def test_empty_saved_list_is_preserved_as_an_intentional_no-elements_choice(): ...
```

**Step 2: Implement minimal configuration**

- Add one `string_list` setting under a dedicated `pageSummaryData` bucket.
- Add helpers that return normalized selected types and save only normalized item types.
- Do not add automatic-page-summary settings in this task.

**Step 3: Run focused and full Web settings harnesses**

```bash
python tests/classic_speech_web_summary_harness.py
python tests/classic_speech_web_settings_harness.py
```

**Step 4: Commit**

```bash
git add _speech_core/plugin_config.py _speech_core/settings/web_summary_config.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: persist web summary element choices"
```

## Task 3: Add the accessible Page Summary settings category

**Objective:** Let users choose included quick-navigation element types through the existing Web / Browse Mode dialog.

**Files:**
- Modify: `_speech_core/settings/web_settings_dialog.py`
- Modify: `tests/classic_speech_web_settings_harness.py`
- Modify: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing dialog tests**

Verify:

```python
def test_web_dialog_exposes_page_summary_category_after_existing_categories(): ...
def test_page_summary_uses_nvda_custom_check_list_box(): ...
def test_page_summary_rows_include_label_keys_and_checked_state(): ...
def test_page_summary_checklist_change_marks_apply_visible_and_enabled(): ...
def test_page_summary_cancel_restores_original_selection(): ...
def test_page_summary_apply_commits_selection_and_resets_cancel_snapshot(): ...
```

**Step 2: Implement the category**

- Extend `CATEGORY_NAMES` with `Page Summary`.
- Add a third scrolled panel; preserve existing category behavior and tab order.
- Bind `wx.EVT_CHECKLISTBOX`, call the normal dirty handler, and call `event.Skip()` so native accessible checklist notifications remain intact.
- Use a dedicated checklist wrapper or helper. Do not reuse token-editor mute/rename semantics.
- Choice labels contain only the element name. Use native checklist state speech: checked means on/included; unchecked means off/excluded.

**Step 3: Run the two focused harnesses**

```bash
python tests/classic_speech_web_summary_harness.py
python tests/classic_speech_web_settings_harness.py
```

**Step 4: Commit**

```bash
git add _speech_core/settings/web_settings_dialog.py tests/classic_speech_web_settings_harness.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: add page summary settings category"
```

## Task 4: Add the on-demand global command

**Objective:** Bind `NVDA+Shift+U` to an on-demand summary without changing normal Browse Mode behavior.

**Files:**
- Modify: `classicSpeech.py`
- Modify: `tests/classic_speech_web_summary_harness.py`

**Step 1: Write failing command tests**

Verify:

```python
def test_nvda_shift_u_is_registered_for_page_summary(): ...
def test_page_summary_uses_active_browse_document_and_selected_types(): ...
def test_non_browse_context_announces_availability_error_only(): ...
def test_command_speaks_the_model_result_without_focus_or_cursor_movement(): ...
def test_command_does_not_register_or_modify_the_normal_speech_filter(): ...
```

**Step 2: Implement minimal command path**

- Add `kb:NVDA+Shift+U` to `GlobalPlugin.__gestures` as the default binding only.
- Add a named script with a clear ClassicSpeech Input Help description and `category="ClassicSpeech"`, so it is listed and fully rebindable in NVDA's Input Gestures dialog.
- Identify the active browse-mode tree interceptor using NVDA APIs, with defensive guards for no document/unsupported iterator cases.
- Ask the model for a result and speak exactly that result through native `ui.message` or the appropriate native speech helper.
- Do not call quick-nav scripts, `QuickNavItem.report`, or `QuickNavItem.moveTo`.

**Step 3: Run focused harness**

```bash
python tests/classic_speech_web_summary_harness.py
```

**Step 4: Commit**

```bash
git add classicSpeech.py tests/classic_speech_web_summary_harness.py
git commit -m "feat: add on-demand web summary command"
```

## Task 5: Run the complete source and CI gate

**Objective:** Verify the feature in the clean source environment before any scratchpad deployment.

**Files:**
- Modify as required only to correct verified failures.

**Step 1: Compile changed modules**

```bash
python -m py_compile classicSpeech.py _speech_core/web_summary.py _speech_core/settings/web_summary_config.py _speech_core/settings/web_settings_dialog.py tests/classic_speech_web_summary_harness.py
```

**Step 2: Run every local harness**

```bash
for test in tests/*harness.py; do python "$test"; done
```

**Step 3: Review scope**

```bash
git diff main...HEAD --check
git diff main...HEAD
git status --short
```

**Step 4: Checkpoint**

Record:

```text
Branch: feat/web-summary-v0
Commits: <list of focused commits>
Source gate: pass/fail
Known limits: no automatic reporting; no browser-specific suppression
Next step: scratchpad deployment only after Tim approves the reviewed source gate
```

## Task 6: Controlled live NVDA validation

**Objective:** Prove that command behavior is useful and non-invasive in real browse-mode documents.

**Files:**
- No source change unless a live defect is reproduced and covered by a new harness first.

**Step 1: Deploy only the verified branch**

Use the normal timestamped scratchpad backup, whole-tree copy, runtime compilation, and source/runtime comparison procedure.

**Step 2: Test Firefox and Chromium with the same representative pages**

For each browser, test:

1. a page containing headings, landmarks, links, and tables;
2. a page with none of the selected types;
3. a page with a long link list;
4. a page with a form;
5. a non-browse context, such as an NVDA dialog.

**Step 3: Confirm non-invasive behavior**

Before and after `NVDA+Shift+U`, confirm:

- focus is unchanged;
- browse cursor is unchanged;
- selected text/caret location is unchanged;
- native page reading continues normally;
- no page-load or automatic announcement occurs.

**Step 4: Record results and decide next action**

Do not merge or push until Tim reviews the live results. If approved, push the feature branch privately, let GitHub Actions verify it, then open a pull request into `main`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A browser does not support one item type | Catch `NotImplementedError` per type; omit it instead of failing the whole summary. |
| Counts are slow on a large page | On-demand only; add a live timing observation before adding any cancellation/limit behavior. |
| Overlapping categories confuse results | v0 excludes visited/unvisited links and heading levels; they can be added later with explicit wording. |
| A summary action changes reading position | The model iterates only; it never reports or moves quick-nav items. |
| Page load timing creates extra speech | v0 has no automatic behavior and no page-load hook. |
| Gesture conflicts in a real setup | Confirm live Input Help/behavior in Firefox and Chromium before final merge. |

## Definition of done

- `NVDA+Shift+U` reports only selected, non-zero count categories from the current supported browse-mode document.
- All requested option labels appear, and the documented canonical choices table preserves their forward and backward quick-navigation key mappings.
- Zero counts are omitted.
- An all-zero result says `No selected element types found.`
- Settings persist and Apply / OK / Cancel work accessibly.
- No automatic reporting control or behavior exists in v0.
- Full local harness gate and GitHub Actions pass.
- Firefox and Chromium live checks confirm no focus/caret/browse-cursor movement and no disruption of ordinary page speech.
