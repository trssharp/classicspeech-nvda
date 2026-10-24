"""Pure, versioned allowlists for audited non-shape presentation domains.

Do not import panels/config here: validation must have no runtime side effects.
"""
import copy

PROFILE_NAMES = ('Beginner', 'Intermediate', 'Advanced')
DETAILS = ('name', 'role', 'state', 'description', 'tooltip')
MENU_DEFAULTS = {
    'announceMenuOpen': True, 'announceMenuClose': True,
    'announceMenuBarFocus': True, 'announceMenuBarLeave': False,
    'menuOpenMessage': 'Entering menu', 'menuCloseMessage': 'Leaving menu',
    'menuBarFocusMessage': 'Menu bar', 'menuBarLeaveMessage': 'Leaving menu bar',
}
HOTKEY_DEFAULTS = {'mode': 'both', 'format': 'native', 'types': 'both', 'dialogAccessKeyOnly': False}
MISC_DEFAULTS = {'includeWindowStateInTitle': False, 'announceDefaultButton': False}
MESSAGE_DEFAULTS = {'browseModeMessage': '', 'focusModeMessage': '', 'passThroughAudioIndication': True}
HOOK_ANNOUNCEMENT_DEFAULTS = {
    'announceSpeechHookLoaded': False, 'speechHookLoadedMessage': 'ClassicSpeech hook loaded',
}
FIELDS = {
    'verbosity': ('version', 'defaultProfile', 'profiles'),
    'menus': ('version',) + tuple(MENU_DEFAULTS),
    'hotkeys': ('version',) + tuple(HOTKEY_DEFAULTS),
    'keyLabels': ('version', 'renames', 'mutedLabels'),
    'misc': ('version',) + tuple(MISC_DEFAULTS),
    'messages': ('version',) + tuple(MESSAGE_DEFAULTS),
    'speechHookAnnouncement': ('version',) + tuple(HOOK_ANNOUNCEMENT_DEFAULTS),
}


def defaults():
    from ...verbosity import VerbosityManager
    from ..profile_config import _default_profile_behavior
    profiles = {}
    for name in PROFILE_NAMES:
        profiles[name] = {
            'enabledTokens': {k: VerbosityManager.PROFILES[name]['enabledTokens'][k] for k in DETAILS},
            **_default_profile_behavior(name),
        }
    return {
        'verbosity': {'version': 1, 'defaultProfile': 'Beginner', 'profiles': profiles},
        'menus': {'version': 1, **MENU_DEFAULTS},
        'hotkeys': {'version': 1, **HOTKEY_DEFAULTS},
        'keyLabels': {'version': 1, 'renames': {}, 'mutedLabels': []},
        'misc': {'version': 1, **MISC_DEFAULTS},
        'messages': {'version': 1, **MESSAGE_DEFAULTS},
        'speechHookAnnouncement': {'version': 1, **HOOK_ANNOUNCEMENT_DEFAULTS},
    }


def _text(value):
    return isinstance(value, str) and len(value) <= 500 and not any(ord(c) < 32 for c in value)


def validate(name, data):
    """Copy only owned leaves. Unknown fields stay opaque in the library."""
    if (not isinstance(data, dict) or type(data.get('version')) is not int
            or data['version'] != 1 or not all(k in data for k in FIELDS[name])):
        raise ValueError('Invalid ' + name + ' presentation domain')
    result = {k: copy.deepcopy(data[k]) for k in FIELDS[name]}
    valid = True
    if name == 'verbosity':
        valid = data['defaultProfile'] in PROFILE_NAMES and isinstance(data['profiles'], dict)
        profiles = {}
        for profile in PROFILE_NAMES:
            row = data['profiles'].get(profile, {}) if isinstance(data['profiles'], dict) else {}
            enabled = row.get('enabledTokens', {}) if isinstance(row, dict) else {}
            if (not isinstance(row, dict) or not isinstance(enabled, dict) or any(type(enabled.get(k)) is not bool for k in DETAILS)
                    or row.get('positionMode') not in ('off', 'first', 'each')
                    or type(row.get('readEditFieldContents')) is not bool):
                valid = False
                continue
            profiles[profile] = {'enabledTokens': {k: enabled[k] for k in DETAILS},
                                 'positionMode': row['positionMode'],
                                 'readEditFieldContents': row['readEditFieldContents']}
        result['profiles'] = profiles
    elif name == 'menus':
        for key, default in MENU_DEFAULTS.items():
            valid &= type(data[key]) is bool if type(default) is bool else _text(data[key]) and bool(data[key].strip())
    elif name == 'hotkeys':
        valid = (data['mode'] in ('off', 'dialogs', 'menus', 'both')
                 and data['format'] in ('native', 'expandedNoPlus', 'abbreviatedNoPlus')
                 and data['types'] in ('access', 'command', 'both', 'none')
                 and type(data['dialogAccessKeyOnly']) is bool)
    elif name == 'keyLabels':
        renames, muted = data['renames'], data['mutedLabels']
        valid = (isinstance(renames, dict) and len(renames) <= 1000
                 and all(_text(k) and k and _text(v) and v.strip() for k, v in renames.items())
                 and isinstance(muted, list) and len(muted) <= 1000
                 and all(_text(k) and k for k in muted))
        if valid:
            result['mutedLabels'] = sorted(set(muted))
    elif name == 'messages':
        valid = (type(data['passThroughAudioIndication']) is bool
                 and _text(data['browseModeMessage']) and _text(data['focusModeMessage']))
    elif name == 'misc':
        valid = all(type(data[k]) is bool for k in MISC_DEFAULTS)
    elif name == 'speechHookAnnouncement':
        valid = (type(data['announceSpeechHookLoaded']) is bool
                 and _text(data['speechHookLoadedMessage']))
    if not valid:
        raise ValueError('Invalid ' + name + ' presentation values')
    return result


def merge_owned(target, source, name):
    """Keep nested future verbosity fields, replace complete rename/mute maps."""
    if name != 'verbosity':
        target.update(copy.deepcopy(source))
        return
    target['version'] = source['version']
    target['defaultProfile'] = source['defaultProfile']
    profiles = target.setdefault('profiles', {})
    for profile, row in source['profiles'].items():
        dest = profiles.setdefault(profile, {})
        dest.setdefault('enabledTokens', {}).update(row['enabledTokens'])
        dest.update({k: v for k, v in row.items() if k != 'enabledTokens'})
