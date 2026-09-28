# ClassicSpeech development changes

These rolling notes cover the changes accumulated on `dev` after the shared
stable-source baseline `09b238f`. That baseline already contains the ClassicSpeech
2.0 release notes and manifest changelog. The historical dev lineage is not a
separate list of new stable 2.0 features; those existing notes remain unchanged.
Development builds are experimental, not stable releases.

## What's new

### Speech and notifications

- Incoming Windows toast announcements omit the leading English "New notification
  from" wording. For the recognized toast layout, they also omit the trailing
  notification count, Actions marker and "window" label. Notification content,
  System Voice routing and raw speech history are preserved; other notification
  layouts and Notification Center are not broadly rewritten.
- Recognized Position tokens such as "1 of 20" follow the existing Number
  Processing choice. Synthesizer-controlled formatting remains unchanged, as do
  each/first/off position reporting and unrelated phone, date and currency options.

### Buttons and settings

- NVDA+E reports an eligible focused push or split button first, including Cancel,
  then falls back to the existing dialog-default and appearance detection. This
  contextual query does not change automatic default-button speech or resolve
  every application's custom Enter behavior. An unresolved query says "No default
  button"; Screen Curtain safeguards remain.
- Unmodified Enter and numpad Enter accept settings from the General and Web /
  Browse Mode category lists and the main Voice Profiles list, using the same save
  action as OK. Other control keys, including focused Cancel and Apply, stay native.

### Updates and development builds

- Advanced settings offer stable (the default) or dev updates alongside the
  existing automatic-check preference. Apply/OK accept the choice; Cancel/Close
  restore the last accepted settings. Turning off automatic checks still allows
  manual checks.
- Development checks use official public prereleases with an add-on and checksum,
  not expiring Actions artifacts. If none exists, ClassicSpeech says so instead
  of falling back to stable. Download locations and asset names are checked.
- Switching channels requires a manual Check for Updates and confirmation,
  including when returning from a date-version dev build to a numerically lower
  stable version. Changing the preference alone does not install anything;
  automatic checks never switch channels or install updates.
- Packages record their installed channel, version and source commit separately
  from the update preference. Development publication is manual-only, verifies a
  pinned dev commit, and creates a unique public prerelease that is never marked
  latest. Dev packages and their publication notes share these accumulated changes;
  stable package notes remain separate.

### Diagnostics

- With debug logging enabled, more speech-filter return paths record their output,
  including Keyboard, Mouse, System notifications, Review and scheme-marked text.
  These records describe filter output before outer scheme processing; logging
  does not change speech routing or history.

## Maintaining these notes

Update this one file as changes land on dev; do not create a README or release-note
file per build. Keep the What's new section concise, user-facing, and compatible
with NVDA's basic Markdown renderer. Packaging and manual publication use the same
section parser. Only `--channel dev` replaces the changelog inside the generated
archive and includes `globalPlugins/docs/DEVELOPMENT.md`; it never synchronizes
these notes into the stable source manifest.

The manual publisher takes both notes and build scripts from its pinned dev
checkout. Each unique release retains that checkout's text, numeric version and
full source commit. Later edits here do not revise existing releases or tags.
When preparing a stable release, curate its own versioned release notes and
synchronize the stable manifest separately. See [Update channels](UPDATE-CHANNELS.md)
for publication instructions and the required main-workflow alignment.
