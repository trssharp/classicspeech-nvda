# ClassicSpeech

ClassicSpeech is an NVDA add-on for configurable speech verbosity, conservative text and number processing, Web / Browse Mode tools, and same-synth Voice Profiles.

> **Current release:** [ClassicSpeech 1.01](https://github.com/trssharp/classicspeech-nvda/releases/tag/v1.01) is the latest stable release. The `main` branch remains active development; commits after a release may not yet have completed live NVDA validation.

## Settings access

All ClassicSpeech settings are available from **NVDA menu → Preferences → ClassicSpeech**:

- **General Settings**
- **Web / Browse Mode Settings**
- **Voice Profiles**

The same three commands appear in NVDA's **Input Gestures** dialog under the **ClassicSpeech** category. They intentionally have **no default gestures**, so they do not compete with gestures supplied by other add-ons. Assign a gesture there only if it suits your configuration.

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

### Voice Profiles

Current Voice Profile categories are:

- **Focus and navigation**
- **Review and object navigation**, including mouse feedback
- **Keyboard entry**
- **System and notifications** for explicitly scoped NVDA system-origin speech

A Voice Profile may select an exposed Voice or Variant and supported synthesizer settings. ClassicSpeech applies a profile only to an owned complete speech sequence, then restores the active synthesizer settings.

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

- ClassicSpeech does **not** automatically change NVDA's selected synthesizer.
- Automatic cross-synth switching is out of scope.
- Voice Profiles are stored separately for each synthesizer.
- Reset all Voice Profile overrides clears every ClassicSpeech profile override for the active synthesizer, returning all categories to native NVDA Voice Settings.
- System routing is source-scoped. ClassicSpeech does not route every NVDA message through a System profile.
- Windows can place notifications in Notification Center without sending NVDA a live accessibility event. ClassicSpeech can only route notification speech that NVDA receives.
- ClassicSpeech does not mutate NVDA virtual buffers or replace native Browse Mode presentation.

## Installation and manual testing

The source manifest currently supports NVDA 2025.1 through 2026.1. Download the `.nvda-addon` from the [latest release](https://github.com/trssharp/classicspeech-nvda/releases/latest), open it in Windows Explorer, and accept NVDA's add-on installation prompt. Restart NVDA when prompted.

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