# ClassicSpeech 2.01

## What's new

- Choose **stable** or **dev** in General Settings > Advanced > **Update from:**. Stable remains the default. Both manual and automatic checks use this preference.
- **Check for updates automatically:** remains enabled by default and checks about 30 seconds after startup, at most once a day. Turning it off does not disable the manual Check for Updates command.
- Development updates come from official public GitHub prereleases, with an add-on and matching SHA-256 file. No GitHub login is needed. If no development release exists, ClassicSpeech says so instead of offering stable as a fallback.
- To switch channels, accept the settings and run **Check for Updates**. A separate confirmation identifies the installed and target versions and channels, including a return from a numerically higher development build to stable. Automatic checks never switch channels, and changing the preference never installs anything.
- Apply and OK accept the update preferences; Cancel and Close restore the last accepted settings. Packages record their source commit and installed build channel separately from the selected update preference.

## Scope

This is an updater-only release based on ClassicSpeech 2.0. Speech processing, voice routing, toast announcements, default-button behavior, diagnostic logging, settings-list Enter behavior, and position-number formatting are unchanged from the stable baseline.

## Installation and verification

Download `ClassicSpeech-2.01.nvda-addon` and its `.sha256` sidecar from this release. The sidecar contains the package checksum. Opening the add-on uses NVDA's own installation and compatibility confirmation; this release does not bypass those checks.

The manifest changelog contains the What's new section above. Automated regression tests cover channel defaults, discovery, preference persistence and dialog transactions, and confirmed channel switching. These checks do not replace live NVDA keyboard, speech, or installation acceptance testing.
