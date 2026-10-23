"""Exact raw owned-leaf rollback for the standalone presentation transaction."""
import copy
import config
from . import domains
from .. import native_state
from .model import FIELDS
from ..config_core import _get_live_verbosity_manager, _to_plain_data
from ...key_labels import apply_key_labels_live, get_key_label_config

HOTKEY_KEYS = ('hotkeyMode', 'hotkeyFormat', 'hotkeyTypes', 'hotkeyDialogAccessKeyOnly')
PATHS = [(k,) for k in (*domains.MENU_DEFAULTS, *domains.MISC_DEFAULTS, *HOTKEY_KEYS,
                        'defaultProfile', 'positionMode', 'readEditFieldContents', 'presentationPresets')]
PATHS += [('shapeData', k) for k in FIELDS]
PATHS += [('keyLabelData', k) for k in ('renames', 'mutedLabels')]
PATHS += [('modeIndicationData', k) for k in ('browseModeMessage', 'focusModeMessage')]
for name in domains.PROFILE_NAMES:
    PATHS += [('profileData', name, 'enabledTokens', key) for key in domains.DETAILS]
    PATHS += [('profileBehaviorData', name, key) for key in ('positionMode', 'readEditFieldContents')]

NATIVE_KEYS = {'presentation': ('reportKeyboardShortcuts', 'reportObjectDescriptions',
                              'reportTooltips', 'reportObjectPositionInformation'),
               'virtualBuffers': ('passThroughAudioIndication',)}


def base():
    try:
        return config.conf.profiles[0]
    except Exception:
        return config.conf


def capture_raw():
    root = base()
    states = {}
    # Include ancestor presence so cancelled previews do not leave empty sections.
    for path in [('classicSpeech',) + p for p in PATHS]:
        node = root
        for depth, key in enumerate(path):
            prefix = path[:depth + 1]
            present = hasattr(node, 'keys') and key in node
            if prefix not in states:
                states[prefix] = (present, _to_plain_data(node[key]) if present else None)
            node = node[key] if present else {}
    return states


def restore_raw(states):
    root = base()
    for path in [('classicSpeech',) + p for p in PATHS]:
        present, value = states[path]
        node = root
        for key in path[:-1]:
            if not hasattr(node.get(key), 'keys'):
                if not present:
                    node = None
                    break
                node[key] = {}
            node = node[key]
        if node is not None:
            if present:
                node[path[-1]] = copy.deepcopy(value)
            else:
                node.pop(path[-1], None)
    # Restore absent or malformed ancestors only when originally not mappings.
    for path in sorted(states, key=len, reverse=True):
        present, value = states[path]
        if hasattr(value, 'keys'):
            continue
        node = root
        for key in path[:-1]:
            node = node.get(key, {})
        if not hasattr(node, 'keys'):
            continue
        if present:
            node[path[-1]] = copy.deepcopy(value)
        elif not node.get(path[-1]):
            node.pop(path[-1], None)


class Transaction:
    def __init__(self):
        self.raw = capture_raw()
        self.native = native_state.capture(NATIVE_KEYS)
        manager = _get_live_verbosity_manager()
        self.runtime = (manager.current_profile, copy.deepcopy(manager.get_profile_config()),
                        manager.announce_default_button) if manager is not None else None

    def restore(self):
        restore_raw(self.raw)
        manager = _get_live_verbosity_manager()
        try:
            if manager is not None and self.runtime is not None:
                manager.current_profile = self.runtime[0]
                manager.set_profile_config(copy.deepcopy(self.runtime[1]), save=False)
                manager.announce_default_button = self.runtime[2]
            apply_key_labels_live(get_key_label_config())
        finally:
            restore_raw(self.raw)
            native_state.restore(self.native)
