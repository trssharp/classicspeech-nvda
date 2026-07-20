"""Sequence-only Voice Profile prosody routing.

This deliberately reads the active synthesizer and persisted ClassicSpeech
snapshots without writing either. It returns speech commands that temporarily
change only rate, pitch, and volume for one semantic token; the caller places
the corresponding default commands immediately after that token.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
from numbers import Real

from speech.commands import EndUtteranceCommand, PitchCommand, RateCommand, VolumeCommand
from .voice_profile_runtime import active_full_profile_trigger


_preview_route_suppressed = ContextVar("classic_speech_preview_route_suppressed", default=False)
_keyboard_entry_route_active = ContextVar("classic_speech_keyboard_entry_route_active", default=False)
_mouse_pointer_route_active = ContextVar("classic_speech_mouse_pointer_route_active", default=False)
_system_notification_route_active = ContextVar("classic_speech_system_notification_route_active", default=False)


@contextmanager
def suppress_profile_prosody_routing():
    """Suppress persisted profile routing while an explicit preview is queued.

    Preview applies its editable snapshot directly to the captured synth. Its
    own utterance must not also receive commands from the last saved profile.
    The context is local to the synchronous ``speech.speak`` call.
    """
    token = _preview_route_suppressed.set(True)
    try:
        yield
    finally:
        _preview_route_suppressed.reset(token)


@contextmanager
def keyboard_entry_profile_routing():
    """Mark only NVDA typed character/word echo for Keyboard profile routing."""
    token = _keyboard_entry_route_active.set(True)
    try:
        yield
    finally:
        _keyboard_entry_route_active.reset(token)


def is_keyboard_entry_profile_routing_active():
    """Return whether the current synchronous speech call is typed entry echo."""
    return _keyboard_entry_route_active.get()


@contextmanager
def mouse_pointer_profile_routing():
    """Mark synchronous speech emitted while NVDA handles a mouseMove event."""
    token = _mouse_pointer_route_active.set(True)
    try:
        yield
    finally:
        _mouse_pointer_route_active.reset(token)


def is_mouse_pointer_profile_routing_active():
    return _mouse_pointer_route_active.get()


@contextmanager
def system_notification_profile_routing():
    """Mark one explicit NVDA system-notification origin."""
    token = _system_notification_route_active.set(True)
    try:
        yield
    finally:
        _system_notification_route_active.reset(token)


def is_system_notification_profile_routing_active():
    return _system_notification_route_active.get()


def profile_id_for_formatter_origin(speech_origin="focus"):
    """Return the one Voice Profile that owns a formatter-produced utterance.

    System notification scope takes precedence over the formatter's ordinary
    focus default. Semantic object navigation explicitly owns Review. All
    remaining formatter speech is Focus/navigation.
    """
    if is_system_notification_profile_routing_active():
        return "systemNotifications"
    if speech_origin == "objectNavigation":
        return "reviewObjectNavigation"
    return "focusNavigation"


_PROSODY_SETTINGS = (
    ("rate", RateCommand),
    ("pitch", PitchCommand),
    ("volume", VolumeCommand),
)


def _base_classic_speech_section():
    """Read the base-only ClassicSpeech section, returning no data on failure."""
    try:
        import config
        return config.conf.profiles[0].get("classicSpeech", {})
    except Exception:
        return {}


def _numeric(value):
    """Return an integer command value only for real, non-boolean values."""
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    return int(value)


def _resolve_profile_snapshot(record):
    """Return the automatic-routing snapshot for one stored profile record.

    New records store a selected voice's native values in ``baseline`` solely
    for editor display and comparison. Automatic routing must mirror Preview:
    set that Voice first so the driver loads its engine defaults, then apply
    only deliberate ``overrides``. Replaying a baseline after Voice would
    overwrite dependent defaults such as IBMTTS Breath. Legacy flat records
    predate this distinction and remain full explicit snapshots.
    """
    if not isinstance(record, dict):
        return None
    baseline = record.get("baseline")
    overrides = record.get("overrides")
    if isinstance(baseline, dict) and isinstance(overrides, dict):
        snapshot = {}
        # Voice and Variant are selectors, not stale dependent settings. Preserve
        # both selected baseline selectors, then let explicit overrides win.
        for selector_id in ("voice", "variant"):
            if selector_id in baseline:
                snapshot[selector_id] = baseline[selector_id]
        snapshot.update(overrides)
        return {setting_id: value for setting_id, value in snapshot.items() if value is not None}
    return record


def _voice_profile_registry():
    """Decode the schema-approved Voice Profiles JSON registry."""
    raw = _base_classic_speech_section().get("voiceProfileData", "{}")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict):
                return decoded
        except (TypeError, ValueError):
            pass
    return {}


def _active_profile_snapshot(profile_id):
    """Return ``(driver, snapshot)`` for one active profile, or ``(None, None)``."""
    try:
        from synthDriverHandler import getSynth
        driver = getSynth()
        synth_name = str(getattr(driver, "name", "") or "")
        registry = _voice_profile_registry()
        record = registry.get(synth_name, {}).get(profile_id)
        snapshot = _resolve_profile_snapshot(record)
        if not isinstance(snapshot, dict):
            return None, None
        # Variants may change a driver's live rate. Carry the current NVDA Rate
        # through selector changes unless this category explicitly chose a Rate.
        if "rate" not in snapshot:
            try:
                import config
                supported = {getattr(setting, "id", "") for setting in getattr(driver, "supportedSettings", ())}
                synth_name = str(getattr(driver, "name", "") or "")
                if "rate" in supported:
                    snapshot = dict(snapshot)
                    snapshot["rate"] = config.conf["speech"][synth_name]["rate"]
            except Exception:
                pass
        return driver, snapshot
    except Exception:
        return None, None


def _configured_synth_value(driver, setting_id):
    """Return NVDA's saved prosody base used by ``BaseProsodyCommand``.

    Speech commands are offsets from ``config.conf["speech"][driver.name]``,
    not from a temporary live driver value changed by Voice Profile Preview.
    """
    try:
        import config
        synth_name = str(getattr(driver, "name", "") or "")
        return _numeric(config.conf["speech"][synth_name][setting_id])
    except Exception:
        return None


def _profile_prosody_commands(profile_id):
    """Build non-mutating begin/reset command lists for one saved profile.

    Only advertised numeric Rate/Pitch/Volume settings that differ from NVDA's
    saved synth configuration participate. The returned commands use offsets
    from the same configured base as NVDA's ``BaseProsodyCommand``, never set
    driver attributes, and pair every begin command with a no-argument reset.
    """
    if _preview_route_suppressed.get():
        return (), ()
    driver, snapshot = _active_profile_snapshot(profile_id)
    if driver is None:
        return (), ()
    try:
        supported = {
            setting.id
            for setting in getattr(driver, "supportedSettings", ())
            if getattr(setting, "id", None)
        }
    except Exception:
        return (), ()

    begin = []
    reset = []
    for setting_id, command_type in _PROSODY_SETTINGS:
        if setting_id not in supported or setting_id not in snapshot:
            continue
        target = _numeric(snapshot[setting_id])
        configured = _configured_synth_value(driver, setting_id)
        if target is None or configured is None or target == configured:
            continue
        begin.append(command_type(offset=target - configured))
        reset.append(command_type())
    return tuple(begin), tuple(reset)


def system_notification_prosody_commands():
    """Build command lists for the active System and notifications profile."""
    return _profile_prosody_commands("systemNotifications")


def review_object_navigation_prosody_commands():
    """Build command lists for an enabled object-navigation announcement."""
    return _profile_prosody_commands("reviewObjectNavigation")


def wrap_profile_sequence(sequence, profile_id, *, fallback_prosody=True):
    """Apply one whole-sequence Voice Profile without parsing native text.

    The native configuration-trigger pair carries every supported active-synth
    setting, including Variant. Rate/pitch/volume-only profiles retain the
    established speech-command fallback below.
    """
    items = list(sequence)
    # NVDA can filter a Review utterance in command-only fragments (for example,
    # language/state commands) before the actual text arrives. They have nothing
    # audible to own, so do not enter and immediately exit a profile transaction.
    if not any(isinstance(item, str) and item for item in items):
        return items
    if _preview_route_suppressed.get():
        return items
    full_trigger = active_full_profile_trigger(profile_id, _active_profile_snapshot)
    if full_trigger is not None:
        # SpeechManager recognises this native command, waits for an utterance
        # boundary, and invokes the same-synth config loader on enter/exit.
        from speech.commands import ConfigProfileTriggerCommand
        return [
            ConfigProfileTriggerCommand(full_trigger, True),
            *items,
            ConfigProfileTriggerCommand(full_trigger, False),
        ]
    if not fallback_prosody:
        return items
    begin, reset = _profile_prosody_commands(profile_id)
    if not begin:
        return items

    wrapped = []
    segment = []

    def append_segment(items_before_boundary):
        text_indexes = [
            index for index, item in enumerate(items_before_boundary)
            if isinstance(item, str) and item
        ]
        if not text_indexes:
            wrapped.extend(items_before_boundary)
            return
        first_text = text_indexes[0]
        last_text = text_indexes[-1]
        profile_pitch = next((command for command in begin if isinstance(command, PitchCommand)), None)
        profile_pitch_offset = profile_pitch.offset if profile_pitch is not None else 0
        non_pitch_begin = tuple(command for command in begin if not isinstance(command, PitchCommand))
        has_native_pitch = profile_pitch is not None and any(
            isinstance(item, PitchCommand) for item in items_before_boundary
        )
        pitch_is_active = False

        for index, item in enumerate(items_before_boundary):
            if isinstance(item, PitchCommand) and profile_pitch is not None:
                # NVDA uses these commands for capitalization. Rebase each one
                # on the Review pitch so its relative rise remains audible.
                wrapped.append(PitchCommand(offset=profile_pitch_offset + item.offset))
                pitch_is_active = True
                continue
            if index == first_text:
                if pitch_is_active:
                    wrapped.extend(non_pitch_begin)
                else:
                    # Preserve the established Rate -> Pitch -> Volume order
                    # when NVDA has not already supplied a pitch command.
                    wrapped.extend(begin)
                    pitch_is_active = profile_pitch is not None
            wrapped.append(item)
            if index == last_text and not has_native_pitch:
                wrapped.extend(reset)
        if has_native_pitch:
            # Keep NVDA's native capital-pitch reset inside the Review baseline,
            # then restore every Review setting before the utterance boundary.
            wrapped.extend(reset)

    for item in items:
        if isinstance(item, EndUtteranceCommand):
            append_segment(segment)
            wrapped.append(item)
            segment = []
        else:
            segment.append(item)
    append_segment(segment)
    return wrapped


def wrap_review_literal_sequence(sequence):
    """Apply Review prosody while preserving native Review Cursor output."""
    return wrap_profile_sequence(sequence, "reviewObjectNavigation")


def wrap_keyboard_entry_sequence(sequence):
    """Apply Keyboard entry prosody while preserving native typed-entry output."""
    return wrap_profile_sequence(sequence, "keyboardEntry")


def wrap_system_notification_sequence(sequence):
    """Apply System profile prosody while preserving native notification output."""
    return wrap_profile_sequence(sequence, "systemNotifications")


def focus_navigation_prosody_commands():
    """Build command lists for the active Focus and navigation profile."""
    return _profile_prosody_commands("focusNavigation")
