# ClassicSpeech

ClassicSpeech is an NVDA add-on for configurable speech verbosity, conservative text and number processing, Web / Browse Mode tools, and same-synth Voice Profiles.

> **Current release:** Download the [latest stable ClassicSpeech release](https://github.com/trssharp/classicspeech-nvda/releases/latest). The `main` branch remains active development; commits after a release may not yet have completed live NVDA validation.

## Settings access

All ClassicSpeech settings are available from **NVDA menu → Preferences → ClassicSpeech**:

- **General Settings**
- **Web / Browse Mode Settings**
- **Voice Profiles**
- **Speech and Sound Schemes**

The same commands appear in NVDA's **Input Gestures** dialog under the **ClassicSpeech** category, together with commands that turn speech and sound schemes on or off, switch to the next scheme, and open the user guide. They intentionally have **no default gestures**, so they do not compete with gestures supplied by other add-ons. Assign a gesture there only if it suits your configuration.

## User guide

The user guide explains every setting and command. Open it from NVDA's **Add-on Store**: on the **Installed add-ons** tab, select ClassicSpeech, press the Applications key or Shift+F10, and choose **Help**. You can also assign a gesture to **Opens the ClassicSpeech user guide** in Input Gestures. The guide's source is [doc/en/readme.html](doc/en/readme.html).

## What it does

### Speech verbosity and formatting

ClassicSpeech can format selected NVDA object-speech details as semantic tokens, including name, role, value, state, position, description, hotkey, and tooltip. The **Spoken object details** checklist uses native NVDA checkbox announcements. Tooltip timing is intentionally unchanged because current speech routes cannot provide reliable full-token timing.

Position announcements are separate from the Position token and are set per verbosity profile:

| Profile | Default position behavior |
| --- | --- |
| Beginner | Announce on every move |
| Intermediate | Announce only the first item in a container |
| Advanced | Off |

The Intermediate profile leaves Description and Hotkey off by default. You can change these choices in **General Settings → Verbosity**.

**Read edit field contents when focused**, also in **General Settings → Verbosity**, is on for every profile by default. Moving to an edit field then speaks its current line, or "blank" when it is empty, as NVDA does natively. Clear it to hear only selected text, which was the behavior in 1.01.

### Voice Profiles

Current Voice Profile categories are:

- **Focus and navigation**
- **Review and object navigation**
- **Mouse**, for speech from NVDA's mouse tracking when you move a physical mouse or touchpad
- **Keyboard entry**
- **System and notifications** for explicitly scoped NVDA system-origin speech
- **Document and web formatting**, a voice for any item from NVDA's Document Formatting panel (font attributes, specific fonts and sizes, document information, pages and spacing, table information, headings and each heading level, links, lists, landmarks and other elements)

A Voice Profile may select an exposed Voice or Variant and supported synthesizer settings. ClassicSpeech applies a profile only to an owned complete speech sequence, then restores the active synthesizer settings.

**Export voice profiles** saves every synthesizer's profiles in one `.classicspeech-voices` file, and **Import voice profiles** reads one, replacing only the synthesizers and categories it contains.

A document and web formatting voice is used for the announcement and for the text itself, such as the bold words or the heading. An item may also use another installed synthesizer. NVDA loads that synthesizer each time the item is spoken, which adds a delay, so the active synthesizer is the fastest choice.

### Speech and Sound Schemes

**Speech and Sound Schemes** works like the JAWS Speech and Sounds Manager. Every NVDA object type and state, unknown objects, unlabeled graphics, window classes you add, and every document formatting and web element option can have:

- a WAV sound, played in addition to the announcement or instead of it;
- a custom voice.

Items are grouped by category, and the dialog has a search box and a filter that shows only the items you changed. Each item's name in the tree says what is set. You can keep several named schemes and switch between them. Sounds and voices apply to focus changes, object navigation, the review cursor, say all, browse mode, and the physical mouse. An item without a sound or voice keeps NVDA's normal speech.

Each scheme, including Default, is its own folder under `ClassicSpeech\Schemes` in NVDA's user configuration folder (`%APPDATA%\nvda\ClassicSpeech\Schemes` for an installed NVDA). A scheme folder holds `scheme.json` and a `Sounds` folder with copies of the scheme's sounds, and **Open schemes folder** shows the folders in File Explorer. **Export scheme** saves a scheme with its sounds as one `.classicspeech-scheme` file, and **Import scheme** adds such a file as a new scheme. Schemes that earlier versions kept in NVDA's configuration move into folders automatically.

### Web / Browse Mode tools

Web / Browse Mode Settings provide ClassicSpeech's Web, Page Summary, Page Ready, heading-continuity, and supported Microsoft Edge notification options alongside the relevant native Browse Mode settings.

**Audio indication of focus and browse modes** is enabled by default and preserves NVDA's native audio indication. When you clear it, **Browse mode message** and **Focus mode message** become available:

- Their initial wording is NVDA's native text: `Browse mode` and `Focus mode`.
- Each message can be customized independently.
- Clearing a custom message restores the native wording for that mode.

### Conservative number processing

Number Processing is opt-in. It changes only standalone whole-number groups, with or without comma separators. Dates, times, currency, phone numbers, fractions, alphanumeric identifiers, and other combined tokens remain native.

For example, `5'5` remains literal rather than becoming `five'five`.

## Safety boundaries

- ClassicSpeech does **not** automatically change NVDA's selected synthesizer. A formatting or scheme item that you set to another synthesizer loads it only for that item's speech, through NVDA's own configuration-profile mechanism, and then returns to your synthesizer.
- Voice Profiles are stored separately for each synthesizer.
- Reset all Voice Profile overrides clears every ClassicSpeech profile override for the active synthesizer, returning all categories to native NVDA Voice Settings.
- System routing is source-scoped. ClassicSpeech does not route every NVDA message through a System profile.
- Windows can place notifications in Notification Center without sending NVDA a live accessibility event. ClassicSpeech can only route notification speech that NVDA receives.
- ClassicSpeech does not mutate NVDA virtual buffers or replace native Browse Mode presentation.

## Installation and manual testing

The source manifest currently supports NVDA 2025.1 through 2026.2. Download the `.nvda-addon` from the [latest release](https://github.com/trssharp/classicspeech-nvda/releases/latest), open it in Windows Explorer, and accept NVDA's add-on installation prompt. Restart NVDA when prompted.

For a manual development test, deploy only a verified source tree to the scratchpad using the process in the [development workflow](docs/DEVELOPMENT-WORKFLOW.md). Do not edit the scratchpad copy as the source of a change.

## Reporting a problem

For ordinary problems, use the [bug-report template](https://github.com/trssharp/classicspeech-nvda/issues/new?template=bug_report.md). Please include:

1. NVDA version and Windows version;
2. active synthesizer and voice/variant;
3. active ClassicSpeech verbosity profile and Voice Profile category, when relevant;
4. exact steps to reproduce;
5. expected versus actual speech;
6. a relevant NVDA log excerpt with personal data removed.

Do not include passwords, API keys, access tokens, private account data, or unredacted sensitive logs in an issue. See [SUPPORT.md](SUPPORT.md) for support boundaries and [SECURITY.md](SECURITY.md) for security reporting.

## Development and verification

The source is organized as an NVDA global plugin with an `_speech_core` package. Local harness scripts live under `tests/` and are intentionally excluded from release archives.

Run the local harness gate from the active source folder:

```bash
for test in tests/*harness.py; do python "$test"; done
```

GitHub Actions runs on pull requests, pushes to `main`, and manual workflow dispatches. It compiles the source, runs every harness against a fresh NVDA source checkout, builds a `.nvda-addon` archive, and uploads the archive with its SHA-256 sidecar. CI does not replace live NVDA or synthesizer validation.

See the [development workflow](docs/DEVELOPMENT-WORKFLOW.md), [current status](docs/ROADMAP-STATUS.md), and [versioning guide](docs/VERSIONING.md).

## License

ClassicSpeech is licensed under the **GNU General Public License, version 2 or later** (`GPL-2.0-or-later`). See [LICENSE](LICENSE) and [NOTICE](NOTICE).