# ClassicSpeech 2.0

Draft release notes for ClassicSpeech 2.0, covering the changes since 1.01 merged in PRs #16 through #39. This release has not yet been published.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

### Speech and navigation fixes

* Speech in Windows Explorer and Open and Save dialogs no longer repeatedly searches for a default button on each file-list focus change. ClassicSpeech also uses NVDA's cached focus ancestors to reduce speech-processing delays.
* Tabbing into an edit field reads its current line, or "blank" when it is empty. **Read edit field contents when focused**, on the Verbosity page, can turn this off separately for each verbosity profile. Address bars also keep their name and contents when NVDA announces a tool bar immediately before them.
* Selecting or unselecting the focused item with **Control+Space** announces "selected" or "not selected", regardless of the **List item state reporting** choice. Announcements while moving between items still follow that choice.
* The keyboard-layout menu that opens while adding an Input Gesture now reads its initial item. Stale, held speech fragments no longer suppress the new menu announcement.
* Speech and Sound Schemes tree items named after roles or states, such as "menu" and "selected", are read instead of being mistaken for speech tokens and dropped.
* **NVDA+E** and **Announce default button in dialogs** identify the dialog's real default button more accurately, including split buttons, rather than assuming the focused button is the default. When the default cannot be determined, NVDA+E can explain what Enter presses or identify a uniquely highlighted button by appearance. The appearance check runs only on request, not during ordinary focus speech; with Screen Curtain enabled, it asks you to turn the curtain off before that check.

### Voice Profiles and Speech and Sound Schemes

* **Voice Profiles** adds **Mouse**, for physical mouse tracking, and **Document and web formatting**, for voices on formatting and web elements. Use settings supported by the active synthesizer, or choose another synthesizer for an item. Switching synthesizers can add noticeable delay.
* **Speech and Sound Schemes** lets you assign WAV sounds, voices, or both to object types, states, window classes, document formatting and web elements. Sounds can accompany or replace spoken announcements. Named schemes, search, a customized-items filter, custom entries and unassigned switching commands help organize the settings.
* Formatting and element voices now work across character, word, line, sentence, paragraph and Say All reading, including LibreOffice. The required formatting is requested without changing your saved Document Formatting choices or adding unwanted spoken formatting. Fixes also preserve voices across element text, support synthesizers with limited inline voice commands, and make object-state and style/color items effective. Replacing an announcement with a sound does not remove the document text.
* Each scheme keeps its settings and copied WAV files in its own folder. **Open schemes folder**, **Export scheme** and **Import scheme** let you locate and share schemes. Voice Profiles also has export and import controls. Existing schemes migrate to the folder format, and custom fonts, sizes, styles and window classes belong to their individual scheme.
* **Reset this item** in Document and web formatting removes the item's voice without deleting its scheme sound.
* The **NVDA sounds** scheme category can replace NVDA's own sounds, including browse/focus mode, suggestions, spelling errors, screen curtain, Remote Access, startup and exit sounds, without modifying NVDA's waves folder. Removing a replacement restores the native sound. Failed replacement startup, shutdown and Windows sign-out sounds fall back safely to NVDA's own files, and sound-handler cleanup preserves other add-ons' handlers.

### Settings and message controls

* ClassicSpeech stores its settings separately in `ClassicSpeech/settings.ini` under NVDA's configuration folder, migrating the previous settings automatically. It backs up the NVDA settings it changes so **Reset All ClassicSpeech Settings** and uninstall can restore them, while preserving subsequent changes you made in NVDA. Updating the add-on keeps ClassicSpeech settings.
* Reset confirmation and update dialogs no longer open inside NVDA's core speech/event pump, fixing the reset freeze. Reset asks for confirmation with **No** as the default.
* Cancelling Web / Browse Mode settings restores the dialog's changes correctly. NVDA settings changed while a Voice Profile speaks are retained, and temporary scheme/voice settings no longer leak into saved synthesizer settings. Voice Profile triggers pause in settings dialogs, apart from explicit scheme previews.
* The Hotkeys options **Speak hotkeys in** and **Which shortcuts to speak** use NVDA's accessible checklists instead of combination-based combo boxes. Menus and Dialogs, and Access keys and Command shortcuts, can each be selected independently. Existing settings remain compatible. ClassicSpeech's other checklists use the same native accessible control.
* **Give ClassicSpeech messages priority over NVDA speech**, on the Misc page, is a new optional setting, off by default. When enabled, it protects ClassicSpeech announcements from automatic interruptions; keyboard, braille and touch input can still stop them. It covers messages such as hook loaded, page ready, page summaries and speech-history replay.

### Help, updates and Spanish translation

* A bundled user guide opens from the Add-on Store's **Help** action. An unassigned **Opens the ClassicSpeech user guide** command is also available in Input Gestures. The guide covers the new settings and commands.
* **Check for Updates...** checks this repository's GitHub releases. Automatic checking is enabled by default and runs once a day after startup; it can be turned off on the Advanced page. Checks do not run on secure screens. Installation verifies the downloaded add-on against its published SHA-256 file and uses NVDA's own installation confirmation.
* Manual update checks distinguish an installed development build from GitHub's latest published release: if your installed version is newer, the message reports both versions instead of calling the local build the latest release. The user guide explains draft/prerelease exclusions, numeric version comparisons and same-version manual installation.
* Update offers show the full release notes in a read-only, multiline **What's new** box. You can navigate, select and copy the text with the keyboard; Tab reaches the buttons and Escape closes the dialog without installing.
* On NVDA 2026.1 and later, the Add-on Store's **What's new** action can display the changelog bundled in the add-on manifest. Older supported NVDA versions ignore that field. Packaging checks that it matches the release notes.
* The Spanish catalog now fills previously untranslated entries for recent features. Follow-up corrections improve meaning, NVDA terminology, examples, translation context and scheme-dialog access keys; the compiled catalog is updated too. Spanish remains open to feedback from fluent speakers and NVDA users.
* Josh Kennedy is credited alongside Tim and Calli in the add-on manifest. A runtime compatibility fix removes an unavailable Python-module dependency that otherwise prevented the folder-based schemes version from loading in NVDA.

## Usage notes and limitations

### Scheme voices and sounds

Open **NVDA menu → Preferences → ClassicSpeech → Speech and Sound Schemes...** to configure a scheme. An item without a configured sound or voice keeps NVDA's normal speech. Prefer the active synthesizer for the fastest voice changes.

Schemes are stored under `ClassicSpeech/Schemes` in NVDA's configuration folder. Exported schemes use `.classicspeech-scheme` files; exported Voice Profiles use `.classicspeech-voices` files. Importing Voice Profiles replaces only the synthesizers and categories included in the file.

A scheme's custom NVDA startup sound requires ClassicSpeech to manage startup and exit playback because NVDA normally plays its startup sound before add-ons load. The previous **Play sounds when starting or exiting NVDA** setting is restored when the custom startup sound is removed, ClassicSpeech is disabled or removed, or settings are reset.

Known limitation: when another computer controls this computer through Remote Access, it may not hear replacement NVDA sounds because the sound is sent by a local file path that does not exist on the controlling computer.

### Updates and release identity

The updater uses the repository URL in the manifest, now set to this ClassicSpeech repository. Published update releases need the add-on and its matching `.sha256` file. An available download still goes through NVDA's confirmation; a check does not silently install an update.

The selected release version is **2.0**, with notes in `RELEASE-2.0.md`. Build the release with `python scripts/package_addon.py --version 2.0`, or enter `2.0` in the workflow's **Release version** field. The resulting package is `ClassicSpeech-2.0.nvda-addon`; its packaged manifest reports version `2.0`. The source manifest keeps its neutral `0.0.0` placeholder, and ordinary CI builds retain their date-and-run versions. The intended GitHub release tag is `v2.0`; building the package does not create or publish that release.

## Pull requests covered

This list records every merged PR from #16 through #39, not just those authored by Josh. There is no PR #25 in the repository's PR listing.

* [#16](https://github.com/trssharp/classicspeech-nvda/pull/16): Explorer latency, edit-field and address-bar fixes; Mouse and document-formatting voices; Speech and Sound Schemes.
* [#17](https://github.com/trssharp/classicspeech-nvda/pull/17): Josh Kennedy's author credit.
* [#18](https://github.com/trssharp/classicspeech-nvda/pull/18): Bundled user guide and opening command; preserve sounds when resetting an item's voice.
* [#19](https://github.com/trssharp/classicspeech-nvda/pull/19): Scheme folders and migration; scheme and Voice Profile export/import.
* [#20](https://github.com/trssharp/classicspeech-nvda/pull/20): Remove the unavailable `filecmp` dependency and add runtime-import checks.
* [#21](https://github.com/trssharp/classicspeech-nvda/pull/21): Separate settings file, NVDA-settings backup, reset/uninstall cleanup and saved-voice protection.
* [#22](https://github.com/trssharp/classicspeech-nvda/pull/22): Preserve settings changed during voice overlays; restore Web / Browse Mode changes on Cancel.
* [#23](https://github.com/trssharp/classicspeech-nvda/pull/23): GitHub update checking and checksum-verified installation.
* [#24](https://github.com/trssharp/classicspeech-nvda/pull/24): Fix reset and update modal-dialog scheduling; default reset confirmation to No.
* [#26](https://github.com/trssharp/classicspeech-nvda/pull/26): Scheme coverage across reading modes, formatting ranges, object states and synthesizer capabilities.
* [#27](https://github.com/trssharp/classicspeech-nvda/pull/27): Full, keyboard-navigable update notes.
* [#28](https://github.com/trssharp/classicspeech-nvda/pull/28): Point the updater at this repository.
* [#29](https://github.com/trssharp/classicspeech-nvda/pull/29): Real default-button detection and on-request appearance fallback.
* [#30](https://github.com/trssharp/classicspeech-nvda/pull/30): Restore the initial Input Gestures menu announcement and discard stale cancellation markers.
* [#31](https://github.com/trssharp/classicspeech-nvda/pull/31): Read scheme-tree row names that resemble roles or states.
* [#32](https://github.com/trssharp/classicspeech-nvda/pull/32): Native accessible Hotkeys checklists and shared checklist controls.
* [#33](https://github.com/trssharp/classicspeech-nvda/pull/33): Manifest changelog and release-note synchronization checks.
* [#34](https://github.com/trssharp/classicspeech-nvda/pull/34): Optional priority for ClassicSpeech messages.
* [#35](https://github.com/trssharp/classicspeech-nvda/pull/35): Scheme replacements for NVDA's own sounds.
* [#36](https://github.com/trssharp/classicspeech-nvda/pull/36): Safe sound-wrapper cleanup and native startup/shutdown fallback.
* [#37](https://github.com/trssharp/classicspeech-nvda/pull/37): Complete the current Spanish catalog, including translation-context and access-key repairs before merge.
* [#38](https://github.com/trssharp/classicspeech-nvda/pull/38): Preserve explicit Control+Space selection announcements.
* [#39](https://github.com/trssharp/classicspeech-nvda/pull/39): Correct Spanish meaning, terminology and examples; rebuild and regression-check the catalog.

## Verification scope

The linked PRs contain their individual automated-test results and any contributor-reported live tests. Those reports are not a claim that every feature in this combined build has received a fresh live NVDA test.

Before publishing, verify the selected build and package, and check the relevant speech, scheme, settings and update paths in live NVDA. Updating these notes does not install the add-on or change NVDA's configuration.
