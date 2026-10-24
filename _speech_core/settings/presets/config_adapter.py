"""Presentation configuration ownership, independent of every settings panel."""
import copy

from . import domains
from .model import FIELDS
from ..config_core import _ensure_classic_speech_section, _as_bool
from ..shape_config import _clone_shape_from_manager, _save_shape_config
from ..profile_config import (
    _clone_profile_from_manager, _get_profile_behavior, _set_active_profile_name,
    _save_profile_behavior, _apply_profile_behavior_runtime, _apply_profile_live,
)
from ..hotkeys_config import (
    _get_hotkey_mode, _get_hotkey_format, _get_hotkey_types, _get_hotkey_dialog_access_key_only,
    _set_hotkey_mode, _set_hotkey_format, _set_hotkey_types, _set_hotkey_dialog_access_key_only,
)
from ..key_labels_config import _save_key_label_config, _preview_key_label_config
from ...key_labels import get_key_label_config
from ..misc_config import _set_default_button_enabled, _set_include_window_state_in_title
from ..web import mode_indication_config as messages
from ..web.formatting_config import get_virtual_buffer_setting, set_virtual_buffer_setting


def capture():
    # Legacy settings getters ensure empty containers. Reading a preset must
    # remain observational, even when those containers were absent on disk.
    from .transaction import capture_raw, restore_raw
    raw = capture_raw()
    try:
        return _capture()
    finally:
        restore_raw(raw)


def _capture():
    conf = _ensure_classic_speech_section()
    profiles = {}
    for name in domains.PROFILE_NAMES:
        enabled = _clone_profile_from_manager(name)['enabledTokens']
        profiles[name] = {'enabledTokens': {k: enabled[k] for k in domains.DETAILS},
                          **_get_profile_behavior(name)}
    return {
        **_clone_shape_from_manager(),
        'verbosity': {'version': 1, 'defaultProfile': conf.get('defaultProfile', 'Beginner'), 'profiles': profiles},
        'menus': {'version': 1, **{k: _as_bool(conf.get(k, v), v) if type(v) is bool
                                 else str(conf.get(k, v)) for k, v in domains.MENU_DEFAULTS.items()}},
        'hotkeys': {'version': 1, 'mode': _get_hotkey_mode(), 'format': _get_hotkey_format(),
                    'types': _get_hotkey_types(), 'dialogAccessKeyOnly': _get_hotkey_dialog_access_key_only()},
        'keyLabels': {'version': 1, **get_key_label_config()},
        'misc': {'version': 1, **{k: _as_bool(conf.get(k, v), v) for k, v in domains.MISC_DEFAULTS.items()}},
        # Preserve stored blank/whitespace text, not the Advanced getter's
        # effective spoken fallback. Capture must not materialize missing keys.
        'speechHookAnnouncement': {'version': 1, **{
            k: _as_bool(conf.get(k, v), v) if type(v) is bool else str(conf.get(k, v) or '')
            for k, v in domains.HOOK_ANNOUNCEMENT_DEFAULTS.items()}},
        'messages': {'version': 1,
                     'browseModeMessage': messages.get_custom_browse_mode_message() or '',
                     'focusModeMessage': messages.get_custom_focus_mode_message() or '',
                     'passThroughAudioIndication': get_virtual_buffer_setting('passThroughAudioIndication')},
    }


def apply(snapshot):
    """Apply only supported present domains; no disk save or hidden controls.

    Profile writes are leaf-scoped: even known but unowned enabled flags and
    unknown future profile fields remain intact. Runtime is rebuilt afterwards.
    """
    from .model import capture as validate
    snapshot = validate(snapshot)
    conf = _ensure_classic_speech_section()
    _save_shape_config({k: snapshot[k] for k in FIELDS})
    if 'verbosity' in snapshot:
        data = snapshot['verbosity']
        for name, row in data['profiles'].items():
            profile = conf['profileData'].setdefault(name, {})
            profile.setdefault('enabledTokens', {}).update(copy.deepcopy(row['enabledTokens']))
            _save_profile_behavior(name, row)
        active = data['defaultProfile']
        _set_active_profile_name(active)
        _apply_profile_live(active)
        _apply_profile_behavior_runtime(_clone_profile_from_manager(active), _get_profile_behavior(active))
    if 'menus' in snapshot:
        conf.update({k: snapshot['menus'][k] for k in domains.MENU_DEFAULTS})
    if 'speechHookAnnouncement' in snapshot:
        # Preference/text only: never invoke the hook lifecycle or play speech.
        conf.update({k: snapshot['speechHookAnnouncement'][k]
                     for k in domains.HOOK_ANNOUNCEMENT_DEFAULTS})
    if 'hotkeys' in snapshot:
        data = snapshot['hotkeys']
        _set_hotkey_mode(data['mode'])
        _set_hotkey_format(data['format'])
        _set_hotkey_types(data['types'])
        _set_hotkey_dialog_access_key_only(data['dialogAccessKeyOnly'])
    if 'keyLabels' in snapshot:
        data = {k: snapshot['keyLabels'][k] for k in ('renames', 'mutedLabels')}
        _save_key_label_config(data)
        _preview_key_label_config(data)
    if 'misc' in snapshot:
        data = snapshot['misc']
        _set_default_button_enabled(data['announceDefaultButton'])
        _set_include_window_state_in_title(data['includeWindowStateInTitle'])
    if 'messages' in snapshot:
        data = snapshot['messages']
        messages.set_browse_mode_message(data['browseModeMessage'])
        messages.set_focus_mode_message(data['focusModeMessage'])
        set_virtual_buffer_setting('passThroughAudioIndication', data['passThroughAudioIndication'])
