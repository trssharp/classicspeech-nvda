# ClassicSpeech development changes

These rolling notes cover the changes accumulated on `dev` after the shared
stable-source baseline `09b238f`. That baseline already contains the ClassicSpeech
2.0 release notes and manifest changelog. The historical dev lineage is not a
separate list of new stable 2.0 features; those existing notes remain unchanged.
Development builds are experimental, not stable releases.

## What's new

### Speech and notifications

- Misc settings offer **Include window state when reporting the title**, off by
  default. NVDA+T on its first press appends the foreground window's normal,
  maximized or minimized state when available. Native spelling and copy keep only
  the title; automatic focus announcements and existing voice routing are unchanged.

- Incoming Windows toast announcements omit the leading English "New notification
  from" wording. For the recognized toast layout, they also omit the trailing
  notification count, Actions marker and "window" label. Notification content,
  System Voice routing and raw speech history are preserved; other notification
  layouts and Notification Center are not broadly rewritten.
- Recognized Position tokens such as "1 of 20" follow the existing Number
  Processing choice. Synthesizer-controlled formatting remains unchanged, as do
  each/first/off position reporting and unrelated phone, date and currency options.

### Presentation presets

- A standalone **Presentation Presets** manager is available from the ClassicSpeech
  Preferences menu and an unbound Input Gestures command. Presets are explicitly
  loaded snapshots, not automatically enforced profiles. Save as, Update, Rename
  and Delete stage the library; protected ClassicSpeech defaults provide a starting
  point. Loading asks before discarding modified settings and announces its result.
  Enter or numpad Enter on the preset list accepts like OK, not Load.
- Presets cover token order, labels and muting; speech timing; all three verbosity
  profiles; menu announcements; hotkeys; key labels; title-window-state and
  default-button announcements; Browse/Focus messages and their audio indication;
  and the Advanced speech-hook startup announcement checkbox and text. Voices,
  schemes, other text/document/web settings, updates and diagnostics are excluded.
  Missing domains leave current settings unchanged. Future fields are preserved
  without applying them, and unsupported libraries remain read-only.
- Import and Export transfer one saved user preset as validated JSON. Import stages
  a new record without loading it; name conflicts ask rather than overwrite.
  Export writes the selected saved record immediately, not unsaved live changes
  or the whole configuration. Apply/OK accepts library edits; Cancel/Close restores
  the last accepted owned settings and runtime state without undoing unrelated
  changes. Persistence still uses NVDA's existing configuration-save boundary.

### Buttons and settings

- The Voice Profiles dialog now auditions the selected category during normal
  dialog speech. Voice, Variant and other supported edits are heard immediately;
  controls follow the voice's actual dependent settings. This stays on the current
  synthesizer and does not change automatic category routing in other dialogs.
  Document and web formatting returns normal dialog speech to the opening voice,
  with its existing explicit item previews retained.
- Explicit Preview remains available and returns to the selected live audition.
  Apply accepts edits and continues auditioning; OK accepts and closes. Cancel,
  Escape and Close discard edits since the last acceptance. Closing always restores
  the opening native voice settings, including after Apply. Saving NVDA configuration
  during audition does not persist the audition as the native voice; delayed work
  is invalidated on close, synthesizer change or plugin unload.
- **Alt+A** consistently activates an available Apply button in General Settings,
  Web / Browse Mode Settings, Voice Profiles, Presentation Presets, and Speech and
  Sound Schemes. Conflicting built-in mnemonics are reassigned; conflicting dynamic
  driver mnemonics are removed without changing their visible text. Apply retains
  its existing transaction and does not close the dialog or force a disk save.

- Automatic Voice Profile and scheme voice changes now all pause while the NVDA
  menu or a settings dialog that suspends NVDA configuration-profile triggers is
  open, including rate, pitch and volume changes. A shown dialog still pauses them
  after switching applications. Speech uses the current NVDA voice; automatic
  routing resumes after closing the menu or dialog. Explicit Preview and the
  dialog-owned Voice Profiles audition described above still work.
  This is a voice-routing bypass, not a disabled speech filter: text formatting,
  scheme sounds and speech history remain active, and native configuration profiles
  are not reset. Existing per-utterance voice restoration is unchanged.
- NVDA+E reports an eligible focused push or split button first, including Cancel,
  then falls back to the existing dialog-default and appearance detection. This
  contextual query does not change automatic default-button speech or resolve
  every application's custom Enter behavior. An unresolved query says "No default
  button"; Screen Curtain safeguards remain.
- Unmodified Enter and numpad Enter accept settings from the General and Web /
  Browse Mode category lists and the main Voice Profiles list, using the same save
  action as OK. Other control keys, including focused Cancel and Apply, stay native.

### Updates and development builds

- Advanced settings offer stable or dev updates alongside the existing
  automatic-check preference. With no saved channel choice, development packages
  default to dev; stable, unknown and legacy builds default to stable. Explicitly
  saved choices are preserved across updates. Apply/OK accept the choice; Cancel/Close
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
