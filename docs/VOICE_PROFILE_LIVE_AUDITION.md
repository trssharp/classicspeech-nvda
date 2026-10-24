# Voice Profiles: dialog-owned live audition

## Scope and prerequisite

This source-only feature is stacked on presentation-presets baseline `e295fc3`.
It does not merge either branch, change automatic category routing, remove
Preview, switch synthesizers, or authorize deployment/restart/publication.

The approved exception to the old passive profile-list contract is **only** the
ClassicSpeech Voice Profiles dialog's deliberately owned audition session.
`shouldSuspendConfigProfileTriggers = True` and the uncached settings-GUI checks
at automatic route generation and queued trigger entry remain unchanged.
NVDA's own Settings retains automatic-category suspension. Ordinary Focus,
Review, Keyboard, Mouse, System and scheme transaction ownership is unchanged.

## Ownership and transitions

- Opening drains pending speech/category transactions, verifies the exact active
  driver object, and captures every advertised public setting before any writes.
  An incomplete capture rejects construction rather than authorizing mutation.
- Selecting a category applies Voice, Variant, other advertised selectors, then
  numeric/Boolean explicit values using public driver setters. Like Preview and
  automatic runtime, inherited numeric baselines are not blindly replayed.
  Controls show actual resulting values. Deliberate non-selector edits remain
  explicit even if equal to an older stored baseline. Selection alone does not
  rewrite the working registry.
- The session persists through ordinary dialog speech and speech cancellation.
  Switching category cancels queued speech, restores the opening native state,
  removes the old overlay, and applies the new selection. Transitions are
  synchronous/main-loop serialized, with reentrancy rejection. It is not a loop
  of short Preview utterances or automatic category routing.
- Public settings are rediscovered after selector writes; dependent choices are
  refreshed in place where the schema remains compatible. Native
  `EnhancedInputSlider`, ranges, line/page steps and slider events are retained.
- The formatting row returns normal dialog speech to the opening native voice;
  its item-specific previews are unchanged. It does not select a new synth.
- Apply accepts profile edits and continues auditioning. OK uses the same save
  path then closes. Cancel/Close rolls back the latest accepted profile baseline.
  Native driver restoration always uses the opening capture, never an applied
  profile. The existing voice-store-before-scheme-store save ordering remains;
  these two stores are not newly claimed to be atomic.

## Save isolation and cleanup

The active driver is **not** passed to `keep_settings_out_of_nvda_config`, whose
existing contract is for separately loaded scheme drivers. No save method or
config-save registration on the active driver is changed. An unnamed same-synth
configuration overlay receives NVDA driver saves instead. Before serialization,
pre-config-save cancels speech, restores native values, discards the audition's
synth leaves and carries unrelated writes to their actual target. No overlay is
left for later pre-config-save handlers: their writes reach the real write target
and the current save's disk payload.

A dialog-lifetime, identity-restored **instance** wrapper around `config.conf.save`
adds a native-valued shield only at save entry when audition is paused (for
example, a repeated save before deferred resumption). The existing native save
body and callback registration/order are unchanged. The audition's pre-save
handler removes that shield before later handlers and disk serialization; a
`finally` cleanup also removes it if save exits early. The active driver's
`saveSettings` itself is not replaced. Only the generation-checked post-save
callback resumes selection. Failed saves leave native values, not the audition,
active until another explicit selection/edit or successful save resumption.
Named/native raw synth leaves and their presence remain intact. Close removes
only this session's own save wrapper, preserving any later wrapper owner.

The dialog-only overlay adapter removes its transient `None` dirty-profile marker
when exiting: NVDA's `AggregatedSection` marks its top profile dirty, but unnamed
profiles are not in `_profileCache`. Pre-existing dirty ownership is preserved.
This extends the existing private profile-stack bridge only for dialog audition;
automatic overlays and runtime sequences are not modified. Reference:
NVDA master `2843e703c`, `config.ConfigManager.save`, `_markWriteProfileDirty`,
`AggregatedSection.__setitem__`, and `AutoSettings.saveSettings`.

Close, direct Destroy and plugin unload invalidate UI/save callback generations
before restoration. Synth-change notification closes ownership without loading or
mutating the replacement driver. Restoration orders all selectors before numeric
values, continues after individual errors and reports failures; an incomplete
restore can be retried but never authorizes a new audition. A driver that
permanently rejects its original public setting cannot be forced to restore it.

Preview remains explicit and indexed. It nests within the current audition,
returns to that audition on completion/cancellation, and is canceled before any
new audition/teardown. Its deferred busy-state release checks controller identity
as well as dialog generation, so an older Preview cannot release a new one.
Unmodified Return/numpad Enter on the profile list still calls OK, not Preview;
button, slider, editor, modifier, Space and navigation handling remains native.

## Verification boundary

`tests/classic_speech_voice_audition_harness.py` starts with a RED missing-module
checkpoint, then exercises the injected persistent controller, real dialog
constructor/handlers and stores with native-shaped control doubles, queued
callbacks, and an extracted **actual reference ConfigManager.save** method with
only actions/disk I/O injected. Existing category/runtime, settings-safety,
Preview, keyboard-list acceptance and packaging harnesses remain required.

These are source/isolated behavior checks, not an audible or wx accessibility
certification. A separately authorized live trial still needs selection narration,
Voice/Variant-dependent defaults, slider speech, rapid arrows, Preview interruption,
external NVDA save, Apply/edit/Cancel, OK, Escape/Close, and original-driver fidelity
with the user's actual synth. No installed NVDA state or scratchpad is changed.
