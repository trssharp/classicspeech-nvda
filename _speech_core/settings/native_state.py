"""Exact native leaves changed by General; no native section/reset snapshot."""
import copy
import config
from .. import nvda_settings_backup as backup

# Four intrinsic preset effects, plus General's pre-existing unrelated Misc controls.
NATIVE_KEYS = {
    'presentation': ('reportKeyboardShortcuts', 'reportObjectDescriptions',
                     'reportTooltips', 'reportObjectPositionInformation',
                     'guessObjectPositionInformationWhenUnavailable'),
    'keyboard': ('speechInterruptForCharacters', 'speechInterruptForEnter'),
}


def capture(keys_by_section=None):
    result = []
    for section, keys in (NATIVE_KEYS if keys_by_section is None else keys_by_section).items():
        path = (section,)
        profile, name, _lasting = backup._write_target(config.conf, path)
        present = section in profile
        result.append((profile, name, section, present,
                       {key: copy.deepcopy(backup._raw_state(profile, path, key)) for key in keys}))
    return result


def restore(snapshot):
    for profile, name, section, present, states in snapshot:
        for key, state in states.items():
            with backup.recording_nvda_change((section,), key, config.conf):
                if state['set']:
                    backup._set_raw(profile, (section,), key, copy.deepcopy(state['value']))
                else:
                    backup._delete_raw(profile, (section,), key)
        if not present and section in profile and not profile[section]:
            del profile[section]
        backup._mark_changed(config.conf, name)
    backup._refresh(config.conf)
