# ClassicSpeech

ClassicSpeech is an NVDA add-on for experimenting with configurable speech verbosity, semantic token formatting, and same-synth Voice Profiles.

> **Release status:** Early release candidate / development project. Test with a known-good NVDA configuration and report problems with enough detail to reproduce them.

## What it does

ClassicSpeech can format selected NVDA object-speech details as semantic tokens, such as name, role, value, state, position, description, and hotkey. It also offers same-synth Voice Profiles for selected speech categories.

Current Voice Profile categories are:

- **Focus and navigation**
- **Review and object navigation**, including mouse feedback
- **Keyboard entry**
- **System and notifications** for explicitly scoped NVDA system-origin speech

A Voice Profile may select an exposed Voice or Variant and supported synthesizer settings. ClassicSpeech applies a profile only to an owned complete speech sequence, then restores the active synthesizer settings.

## Safety boundaries

- ClassicSpeech does **not** automatically change NVDA's selected synthesizer.
- Automatic cross-synth switching is out of scope.
- Voice Profiles are stored separately for each synthesizer.
- Resetting a Voice Profile returns that category to native NVDA Voice Settings.
- System routing is source-scoped. ClassicSpeech does not route every NVDA message through a System profile.
- Windows can place notifications in Notification Center without sending NVDA a live accessibility event. ClassicSpeech can only route notification speech that NVDA receives.

## Position announcement defaults

Position announcement behavior is separate from the Position token and is set per verbosity profile:

| Profile | Default behavior |
| --- | --- |
| Beginner | Announce on every move |
| Intermediate | Announce only the first item in a container |
| Advanced | Off |

You can change this at **NVDA menu → Preferences → ClassicSpeech → Verbosity → Position announcements**.

## Installation

1. Download a `.nvda-addon` file from the project’s GitHub Releases page.
2. Open the downloaded file in Windows Explorer.
3. Accept NVDA’s add-on installation prompt.
4. Restart NVDA when prompted.

The current local release candidate is built for NVDA 2025.1 through 2026.1.

## Current RC verification

The current RC has been verified with:

- ClassicSpeech’s complete local harness gate;
- package-structure and compilation checks;
- scratchpad deployment source/runtime comparison;
- live Voice Profile, System notification, and NVDA Remote checks.

## Reporting a problem

Please include:

1. NVDA version and Windows version;
2. active synthesizer and voice/variant;
3. which ClassicSpeech verbosity profile and Voice Profile category were active;
4. exact steps to reproduce;
5. expected versus actual speech;
6. a relevant NVDA log excerpt, with personal data removed.

Do not include passwords, API keys, access tokens, or private account data in an issue or log.

## Development

The source is organized as an NVDA global plugin with an `_speech_core` package. Local harness scripts live under `tests/` and are intentionally excluded from release archives.

Before publishing a change, run the project harnesses from the active source folder:

```bash
for test in tests/*harness.py; do python "$test"; done
```

A GitHub Actions workflow can run these Python checks and build a `.nvda-addon` archive on every tagged release. It cannot replace live NVDA/synthesizer validation, but it can make the package reproducible and prevent malformed release uploads.

## License

A license has not yet been selected for this project. Until one is added, GitHub will show the repository as having no explicit open-source license.
