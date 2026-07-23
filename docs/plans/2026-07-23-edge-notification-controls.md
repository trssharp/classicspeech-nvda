# Edge Notification Controls Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the notification-management portion of MSEdgeDiscardAnnouncements with a permanent, accessible ClassicSpeech Edge panel using the established Token Editor checklist interaction.

**Architecture:** Store a fixed registry of unique Edge UIA Activity IDs in a ClassicSpeech base-only config bucket. A permanent Web / Browse Mode dialog category exposes each activity as a native checklist item: Space enables/suppresses it, F2 edits its optional replacement message, and Delete removes that replacement so native Edge wording returns. An Edge-only `appModules/msedge.py` reads the configuration for every relevant notification and either preserves native NVDA handling, suppresses the exact event, or supplies exactly one replacement message.

**Tech Stack:** Python 3.11; NVDA add-on APIs; wxPython/NVDA controls; existing ClassicSpeech harness scripts and package builder.

---

## Requirements and fixed decisions

- Replicate every **ordinary UIA notification** from the installed MSEdgeDiscardAnnouncements add-on, but collapse its duplicate `UpdateNotification` entry into one activity.
- Exclude `ShowSuggestions`, `CustomUIATextInfo`, editable-text COM recovery, and other overlay/object behavior: they are not ordinary notification controls.
- Use a permanent dialog category named `Microsoft Edge Notifications`; it must appear without Edge running.
- Preserve the installed add-on's effective defaults: seven enabled/native IDs and twenty suppressed IDs; `UpdateNotification` is enabled by default because the duplicate add-on config resolves to its later `true` definition.
- The fixed activity registry is canonical. Save stable IDs, never display labels. Unknown IDs/config entries are discarded safely.
- Checklist semantic: checked is **announce**, unchecked is **suppress**. A custom message applies only to a checked item. F2 does not implicitly enable a suppressed item, matching Token Editor’s independent mute and rename state.
- A recognized enabled activity with no custom message calls `nextHandler()` exactly once. A suppressed ID, or an enabled ID with a custom message, does not call native handling. Custom messages use `ui.message` exactly once.
- Keep Page Ready unchanged: it remains a shared Browse Mode buffer-ready feature, not an Edge UIA notification.
- App-module name collision is expected with the installed MSEdgeDiscardAnnouncements add-on. Never test both implementations enabled; deployment/live testing must temporarily disable the old add-on without deleting it.

## Canonical ordinary Activity IDs

**Page, tab, and navigation:** `PageLoading`, `RefreshingPage`, `ClosingTab`, `OpeningNewTab`, `OpeningWindow`, `OpeningInPrivateWindow`, `GoingBack`, `GoingForward`, `CantGoBack`, `CantGoForward`.

**Downloads:** `HubDownloadsNewDownload`, `HubDownloadsCompleteState`, `HubDownloadsInProgressState`, `HubDownloadsIndeterminateProgressState`.

**Toolbar, search, and browser notices:** `ToolbarButtonRemoved`, `SearchMode`, `SearchModeAvailable`, `NotificationAppear`, `UpdateNotification`, `PageZoom`.

**Autofill and site-content notices:** `Autofill option here`, `AutofillSuggestionFilled`, `PopupClosed`, `AutofillSuggestionHideButton`, `RemoveSuggestion`, `ContentSettingNotification`, `ExcelAutofillSuggestionTriggered`.

Enabled/native defaults: `HubDownloadsNewDownload`, `HubDownloadsCompleteState`, `PageZoom`, `RemoveSuggestion`, `ContentSettingNotification`, `ExcelAutofillSuggestionTriggered`, `UpdateNotification`. All other listed IDs default suppressed.

---

### Task 1: Add the registry and normalized persistent configuration

**Objective:** Establish the one source of truth for all 27 unique supported Activity IDs, their display labels, effective defaults, and custom-message persistence.

**Files:**
- Create: `_speech_core/settings/edge_notifications_config.py`
- Modify: `_speech_core/plugin_config.py`
- Create: `tests/classic_speech_edge_notifications_harness.py`

**Step 1: Write failing harness coverage**

Assert the registry has 27 unique IDs, includes one `UpdateNotification`, excludes `ShowSuggestions`, preserves registry order, has the seven effective enabled defaults, normalizes malformed/unknown/duplicate IDs, trims messages, and retains a custom message independently of checked state.

**Step 2: Run the focused harness and verify failure**

Run: `python tests/classic_speech_edge_notifications_harness.py`

Expected: failure because the registry/config module does not exist.

**Step 3: Add the ConfigObj schema and minimal helpers**

Add `classicSpeech.edgeNotificationData` to `_speech_core/plugin_config.py`:

```python
"edgeNotificationData": {
    "enabledActivityIds": "string_list(default=list(...seven effective defaults...))",
    "customMessages": {"__many__": "string(default='')"},
},
```

Implement registry-backed getters/setters plus a snapshot/restore helper in `edge_notifications_config.py`. Missing/malformed data must resolve to the effective defaults; a deliberately empty enabled list must remain empty.

**Step 4: Re-run focused harness**

Run: `python tests/classic_speech_edge_notifications_harness.py`

Expected: config/registry tests pass.

**Step 5: Commit**

```bash
git add _speech_core/plugin_config.py _speech_core/settings/edge_notifications_config.py tests/classic_speech_edge_notifications_harness.py
git commit -m "feat: add Edge notification configuration"
```

### Task 2: Reuse the Token Editor interaction for Edge notification rows

**Objective:** Provide a semantically accurate reusable checklist editor without misleading token-specific wording.

**Files:**
- Modify: `_speech_core/settings/rename_list_panel.py`
- Create: `_speech_core/settings/edge_notifications_panel.py`
- Modify: `tests/classic_speech_edge_notifications_harness.py`

**Step 1: Write failing editor tests**

Use lightweight fake wx controls to assert that Edge rows display compact item labels, Space toggles checked state, F2 prompts with `Custom notification message`, Delete clears only that custom message, and the change callback fires for each mutation.

**Step 2: Run focused harness and verify failure**

Run: `python tests/classic_speech_edge_notifications_harness.py`

Expected: failure because the Edge editor/panel does not exist.

**Step 3: Generalize only the reusable mechanics**

Add optional prompt/status/description hooks to `RenameListPanel`, preserving current Token Editor and Key Labels wording/tests unchanged. Build `EdgeNotificationsPanel` on that component with this panel description:

```text
Space: announce or suppress. F2: set a custom announcement. Delete: restore the native Edge announcement. Shift+F10: menu.
```

Rows use friendly labels; native checklist state conveys enabled/suppressed. A row with a custom message adds only `custom message: …` context.

**Step 4: Re-run focused and existing editor tests**

Run:

```bash
python tests/classic_speech_edge_notifications_harness.py
python tests/classic_speech_core_harness.py
```

Expected: all pass.

**Step 5: Commit**

```bash
git add _speech_core/settings/rename_list_panel.py _speech_core/settings/edge_notifications_panel.py tests/classic_speech_edge_notifications_harness.py
git commit -m "feat: add editable Edge notification list"
```

### Task 3: Integrate a permanent Web / Browse Mode category with live transaction semantics

**Objective:** Add the editor to the ClassicSpeech dialog unconditionally and preserve Apply/OK/Cancel/Close behavior.

**Files:**
- Modify: `_speech_core/settings/web_settings_dialog.py`
- Modify: `tests/classic_speech_web_settings_harness.py`
- Modify: `tests/classic_speech_edge_notifications_harness.py`

**Step 1: Write failing dialog tests**

Assert `Microsoft Edge Notifications` is the fourth permanent category; the panel is always constructed and included in `dynamicPanels`; edits apply live; Apply advances its restore point; Cancel and window Close restore the saved Edge snapshot.

**Step 2: Run focused dialog harnesses and verify failure**

Run:

```bash
python tests/classic_speech_web_settings_harness.py
python tests/classic_speech_edge_notifications_harness.py
```

Expected: category/transaction assertions fail.

**Step 3: Add integration**

Capture the Edge snapshot during dialog initialization. Build/load the Edge panel without testing whether Edge is running. In `_apply_to_config`, save the panel’s working enabled IDs/messages. On Apply refresh its original snapshot; on Cancel/Close restore it. Bind mutations to the dialog’s existing live-Apply/dirty path.

**Step 4: Re-run dialog harnesses**

Run the two focused harnesses above.

Expected: all pass.

**Step 5: Commit**

```bash
git add _speech_core/settings/web_settings_dialog.py tests/classic_speech_web_settings_harness.py tests/classic_speech_edge_notifications_harness.py
git commit -m "feat: add permanent Edge notifications panel"
```

### Task 4: Add the narrow Edge app module and package it

**Objective:** Enforce exact per-Activity-ID behavior only inside Edge and ship it in the archive.

**Files:**
- Create: `appModules/msedge.py`
- Modify: `scripts/package_addon.py`
- Modify: `tests/classic_speech_edge_notifications_harness.py`

**Step 1: Write failing event-contract and package tests**

Stub `ui.message`, `nextHandler`, and config access. Assert unknown/None Activity IDs call native handling once; suppressed recognized IDs do nothing; enabled custom IDs speak once and skip native; enabled native IDs call native once; runtime changes are read per event. Assert the generated `.nvda-addon` contains `appModules/msedge.py` and no cache files.

**Step 2: Run focused harness and verify failure**

Run: `python tests/classic_speech_edge_notifications_harness.py`

Expected: missing app-module/package assertions fail.

**Step 3: Implement narrow event handling**

Create only `event_UIA_notification` with a current-compatible signature accepting optional positional/keyword arguments and `**kwargs`. Guard null/malformed IDs. Do not add overlay classes, `event_NVDAObject_init`, `comtypes`, or generic speech filtering.

Update packaging so app modules go to archive-root `appModules/`, not `globalPlugins/appModules/`, and verify that exact package member.

**Step 4: Run focused tests and build a test archive**

Run:

```bash
python tests/classic_speech_edge_notifications_harness.py
python scripts/package_addon.py --date 2026-07-23
```

Expected: harness passes and package verifies cleanly.

**Step 5: Commit**

```bash
git add appModules/msedge.py scripts/package_addon.py tests/classic_speech_edge_notifications_harness.py
git commit -m "feat: handle configurable Edge UIA notifications"
```

### Task 5: Add the remaining narrow Edge compatibility behaviors

**Objective:** Make ClassicSpeech a practical replacement for the unavailable Edge add-on without pretending its object/COM behavior is an ordinary notification control.

**Files:**
- Modify: `appModules/msedge.py`
- Modify: `_speech_core/settings/edge_notifications_config.py`
- Modify: `_speech_core/settings/edge_notifications_panel.py`
- Modify: `tests/classic_speech_edge_notifications_harness.py`

**Step 1: Write failing compatibility tests**

Cover two separate requirements:

1. `ShowSuggestions` compatibility applies only to Edge UIA objects with class name `OmniboxResultView`, only when its dedicated address-bar-suggestions option is disabled, and never changes the normal Activity-ID notification registry.
2. The editable-text recovery applies only to Edge UIA editable-text objects with class name `OmniboxViewViews` or `Textfield`; a `comtypes.COMError` from endpoint comparison/caret processing is contained without affecting ordinary editable controls or non-COM exceptions.

**Step 2: Add a separate, clear panel control**

Do not place `ShowSuggestions` in the notification checklist or give it F2/Deletion semantics. Add one normal permanent checkbox below the notification list:

```text
Show address-bar suggestions while typing
```

Preserve the installed add-on's effective default: checked/enabled. It controls only the narrow Omnibox object behavior.

**Step 3: Reimplement behavior narrowly**

Add no broad overlay or generic UIA patches. Use a small Edge-only overlay/recovery class and guard on the exact current UIA class names and editable-text role. Retain normal NVDA behavior whenever no `comtypes.COMError` occurs. Put the compatibility reason in comments and add original-source attribution in project notices if required by the final licensing review.

**Step 4: Verify through an explicit live Edge address-bar trial**

After the notification module is independently verified, test address-bar suggestions and caret movement in current Edge with the external add-on disabled. If current Edge no longer produces the old failure or the behavior is harmful, remove or defer the unproven compatibility path rather than shipping a speculative workaround.

### Task 6: Integration validation and controlled live trial

**Objective:** Prove all existing functionality remains intact and Edge notification controls work without the competing add-on.

**Files:**
- Test: all `tests/*harness.py`
- Test: generated `.nvda-addon` archive
- Deploy target after explicit deployment decision: actual verified NVDA Scratchpad layout

**Step 1: Run static and full regression gates**

```bash
python -m compileall -q classicSpeech.py page_orientation_runtime.py _speech_core appModules
python tests/classic_speech_edge_notifications_harness.py
for test in tests/*harness.py; do python "$test"; done
python scripts/package_addon.py --date 2026-07-23
git diff --check
git status --short --branch
```

Expected: all harnesses and compilation pass, archive has the root `appModules/msedge.py` member, no whitespace errors.

**Step 2: Independent review gates**

Use a specification reviewer first, then a code-quality reviewer. Resolve all Critical and Important issues and rerun affected harnesses.

**Step 3: Prepare a reversible Scratchpad trial**

Verify the actual Scratchpad layout, back up only the affected ClassicSpeech files, and temporarily disable—not delete—the installed MSEdgeDiscardAnnouncements add-on. Do not attempt live testing until no `appModules.msedge` collision remains.

**Step 4: Live test Edge interactions**

Confirm category accessibility and the three modes using real Edge events: a default-suppressed page-load event, a checked native event, and a checked custom replacement. Confirm the external add-on is restored/left available after the trial.

**Step 5: Final commit and upload only after verification**

```bash
git add docs/plans/2026-07-23-edge-notification-controls.md
git commit -m "docs: plan Edge notification controls"
git push --set-upstream origin feat/edge-notification-controls
```
