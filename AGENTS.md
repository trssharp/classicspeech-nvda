# ClassicSpeech for NVDA — Agent Guide

## Scope and source of truth

- Active repository: `classicspeech-nvda`.
- Project roadmap/spec: `../spec.docx`.
- New work belongs in this repository, on a focused Git branch from `main`.
- Do not create independent repository copies, branch-named source folders, or a new `vNN` source folder for ordinary feature work. The historical/versioned folders outside this repository are reference material, not active workspaces.
- Use a separate managed Git worktree only when explicitly needed for a long-lived parallel experiment or comparison.
- After a pull request is merged, remove its temporary worktree and delete its unneeded local branch. Run `git worktree list` first so an active worktree is never removed accidentally.
- Preserve important build artifacts through GitHub Releases or `Classic Speech Historical` before removing a worktree. Generated `dist` output is not source history.

## Delivery boundaries

- ClassicSpeech is an NVDA add-on. Do not modify NVDA core or the installed NVDA baseline unless Tim explicitly requests a separately scoped NVDA-core experiment.
- Keep changes narrow and preserve native NVDA behavior unless the specification explicitly changes it.
- Preserve native literal/review/caret/Say All behavior. Do not route ordinary document text through ClassicSpeech processing without a defined, tested requirement.
- Speech and Sound Schemes (`_speech_core/schemes`) are that kind of defined requirement: they may mark NVDA speech only for items a user configured, and NVDA's output must stay unchanged when nothing is configured (`tests/classic_speech_schemes_harness.py`).
- Each speech and sound scheme is a folder under `ClassicSpeech/Schemes` in NVDA's configuration folder (`_speech_core/schemes/store.py`). Tests that use scheme folders must set `store._ROOT_OVERRIDE` to a temporary folder, never NVDA's real configuration.
- ClassicSpeech's own settings are saved in `ClassicSpeech/settings.ini`, never in nvda.ini (`_speech_core/settings_file.py`). Tests that touch that folder must set `nvda_settings_backup._CONFIG_FOLDER_OVERRIDE` to a temporary folder.
- Change NVDA's own settings only through `nvda_settings_backup.set_nvda_setting` or `recording_nvda_change`, so Reset All ClassicSpeech Settings and removal (`installTasks.py`) can put them back. A synthesizer loaded only to speak or edit a scheme voice must go through `keep_settings_out_of_nvda_config`, so its settings never become the user's NVDA voice settings.
- Voice profile and scheme voices push a temporary, unnamed profile onto NVDA's configuration while they speak (`voice_profile_overlay.py`, `voice_profile_trigger.py`). Such a trigger must stay out of the way of NVDA's settings. It does nothing while `gui.shouldConfigProfileTriggersBeSuspended()` is true, except for a preview. On exit it carries NVDA's writes into the real configuration, apart from the overlay's own voice settings. ClassicSpeech's settings dialogs set `shouldSuspendConfigProfileTriggers = True`, as NVDA's do (`tests/classic_speech_settings_safety_harness.py`).
- Check NVDA's uncached trigger-suspension predicate both when generating automatic voice routes and when queued triggers enter. Do not substitute foreground-window detection; preserve the explicit Preview exception.
- `installTasks.py` removes ClassicSpeech's settings only when the add-on is removed, never when a new version replaces it. It loads `nvda_settings_backup.py` on its own, so that module must not import other ClassicSpeech modules.
- Update checks (`_speech_core/update_check.py`) use the GitHub repository in the manifest `url`. Tests must never reach the network.
- ClassicSpeech speaks its own messages through `message_priority.speak_message` (or `speak_sequence` for speech history), never `ui.message` directly, so **Give ClassicSpeech messages priority over NVDA speech** covers them. With it off they are `ui.message` unchanged. Its `inputCore.decide_executeGesture` handler must always return True, or NVDA would ignore the keyboard (`tests/classic_speech_message_priority_harness.py`).
- NVDA's own sounds are replaced only by wrapping `nvwave.playWaveFile` (`_speech_core/schemes/nvda_sounds.py`), with sounds inside the schemes folder; never write to NVDA's waves folder. NVDA sound items (`nvdaSound.*`) are not speech and stay out of the speech runtime. For a scheme's NVDA start sound, ClassicSpeech turns off NVDA's Play sounds when starting or exiting NVDA through `nvda_settings_backup` and gives it back when the scheme no longer has one, when ClassicSpeech is disabled or removed, and on reset (`tests/classic_speech_nvda_sounds_harness.py`).
- Speech-path code must not walk `obj.parent` chains for the focus; use `_speech_core/focus_ancestry.py`, which reads NVDA's cached focus ancestors (`tests/classic_speech_latency_harness.py`).
- For NVDA+E, report an eligible focused push/split button first; otherwise retain dialog-default detection and the appearance/Screen Curtain fallback. This query-only priority must not alter permanent-default caching or automatic focus announcements, and is not a general application Enter-action resolver. Permanent-default lookup uses standard dialogs' `DM_GETDEFID`, NVDA wx dialogs' own default item rather than a temporary focused default, and existing accessibility detection. Window-handle calls go through `win32_default_button.get_api()`, which only a running NVDA turns on; tests install fakes (`tests/classic_speech_default_button_harness.py`).
- The appearance check (`_speech_core/default_button_appearance.py`) reads screen pixels only for NVDA+E, never for focus speech, and only when nothing else names a default button. It names a button only when that button alone is colored, and says so; with the Screen Curtain on it asks the user to turn the curtain off.
- The token editor owns speech-token ordering and placement. Text Processing owns reporting/filtering transformations; do not move token-placement policy into it.
- Notification handling must remain source-scoped: dedicated Windows toast-arrival methods and explicitly allowlisted Edge UIA Activity IDs, not generic scriptless speech. These are separate scopes. Toast cleanup changes only recognized presentation text; preserve native delivery behavior, existing System Voice/scheme routing, command order, and raw history. Remove only the exact native prefix and recognized terminal scaffolding; leave unknown layouts native.
- `sequence_merger.py` was removed after an audit confirmed it had no active dependents. Do not reintroduce sequence-merging behavior without a defined, tested requirement.

## Accessibility and settings

- The target user is visually impaired. Prefer native NVDA controls, keyboard-complete workflows, stable labels, and screen-reader-friendly feedback.
- Follow existing settings-dialog transaction behavior: Apply, OK, Cancel, Close, reload, and external configuration save must leave persisted and runtime state coherent.
- Scoped settings rollback must restore owned raw values and presence, runtime state, and actual native write-target leaves without overwriting unrelated changes. Deferred GUI callbacks must revalidate owner/request identity and control liveness, and become inert after reload, destruction, or plugin unload; cleanup must be idempotent.
- Presentation presets are passive, explicitly loaded, allowlisted versioned snapshots, not continuously enforced profiles or whole-settings dumps. Missing supported domains leave current values unchanged; preserve unknown fields/domains without applying them, and preserve unsupported library payloads read-only. Do not introduce immediate disk saves. Keep the exact supported-domain inventory in `docs/PRESENTATION_PRESETS.md`.
- In ClassicSpeech settings dialogs, unmodified Enter and numpad Enter on category, profile, or preset lists must invoke the existing OK/save transaction, not Load or Preview. Reuse the scoped list-acceptance helper; preserve native handling for focused buttons (including Cancel and Apply), modifiers, Space, arrows, and editor controls. Every new dialog must have behavioral regression coverage for list acceptance and unchanged non-list handling.
- Do not replace an NVDA accessibility-enhanced control with a raw wx equivalent without explicit approval.
- Never open a modal dialog (a message box or `ShowModal`) from code that runs inside NVDA's core pump, such as a script or a `queueHandler.queueFunction` callback. NVDA's pump doesn't re-enter, so NVDA freezes and can't even speak the dialog; the Reset All ClassicSpeech Settings confirmation did this. Open it with `wx.CallAfter`, as `GlobalPlugin._outside_nvda_core` does (`tests/classic_speech_settings_removal_harness.py`).
- `doc/en/readme.html` is the user guide NVDA opens from the Add-on Store's Help action. Update it with every user-facing change; `tests/classic_speech_user_guide_harness.py` checks that it covers every command, default gesture and settings page.

## Validation

- Read the relevant specification and trace existing code/tests before editing.
- Add or extend focused harness coverage before changing subtle speech-filter, settings, or routing behavior.
- At minimum, compile changed Python files and run the relevant project harnesses/tests.
- Static tests do not prove speech behavior: clearly distinguish them from a live NVDA validation. Never restart NVDA automatically.
- ClassicSpeech runs on NVDA's bundled Python, which lacks some standard library modules; 1.05 failed to load because it imported `filecmp`. Runtime code may import only modules NVDA ships, which `tests/classic_speech_runtime_imports_harness.py` checks.
- Before a release candidate, run the project packaging and archive-member checks; report the exact output path and checksum.
- Every release carries its What's new in the `changelog` of `manifest.ini`, the field NVDA 2026.1 added and shows from the Add-on Store's **What's new** action. The changelog is the `## What's new` section of the release notes `RELEASE_NOTES` names in `scripts/package_addon.py`. Write that section for each release, point `RELEASE_NOTES` at the new notes, and run `python scripts/package_addon.py --sync-changelog`. Packaging refuses a missing or stale changelog, and a release version whose notes `RELEASE_NOTES` isn't (`tests/classic_speech_packaging_harness.py`). Keep the section user-facing, and use only what NVDA's Python-Markdown converts without extensions: headings, lists, emphasis, code and links, but no tables, fenced code blocks, `"""` or `%(`.

## Scratchpad and live validation

- Work in the Git checkout, not directly in the NVDA scratchpad.
- Deploy to scratchpad only when Tim explicitly requests a working/runtime build. Make a timestamped backup, compare source with deployed files, compile the deployed entry points, and do not restart NVDA automatically.
- Preserve the installed NVDA baseline. Scratchpad testing and installed-add-on testing must not be mixed in one trial.

## Git hygiene

- Check `git status` and the active branch before editing.
- Do not commit, push, rebase, force-push, or rewrite history unless Tim explicitly requests it.
- Keep unrelated working-tree changes untouched and report them separately.
- Do not place secrets, logs, runtime backups, or generated artifacts under version control.

## Information placement

- Put stable, repository-specific rules in this file.
- Put reusable cross-project procedures in a Hermes skill.
- Keep personal preferences, account details, and temporary task state out of this repository.
