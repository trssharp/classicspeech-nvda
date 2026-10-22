"""Scoped capture/application and working-copy refresh for General's owned domains."""
import copy
from . import domains
from ..config_core import _ensure_classic_speech_section
from ..misc_config import _set_default_button_enabled, _set_include_window_state_in_title
from ..key_labels_config import _save_key_label_config, _preview_key_label_config


def capture(dialog):
    v = dialog.verbosityPanel
    active = v.get_working_profile_name()
    v.get_working_profile_config()  # Flush the visible controls into the registry.
    profiles = {}
    for name in domains.PROFILE_NAMES:
        config = v.workingProfiles[name]
        behavior = v.workingBehaviors[name]
        profiles[name] = {
            'enabledTokens': {k: config['enabledTokens'][k] for k in domains.DETAILS},
            'positionMode': behavior['positionMode'],
            'readEditFieldContents': behavior['readEditFieldContents'],
        }
    menus = {}
    for key, default in domains.MENU_DEFAULTS.items():
        value = getattr(dialog.menusPanel, key).GetValue()
        menus[key] = bool(value) if type(default) is bool else value.strip() or default
    result = {
        'verbosity': {'version': 1, 'defaultProfile': active, 'profiles': profiles},
        'menus': {'version': 1, **menus},
        'hotkeys': {'version': 1, **dialog.hotkeysPanel.get_working_hotkey_config()},
        'keyLabels': {'version': 1, **dialog.keyLabelsPanel.get_working_key_label_config()},
        'misc': {'version': 1, **{k: bool(getattr(dialog.miscPanel, k).GetValue()) for k in domains.MISC_DEFAULTS}},
    }
    # Capture must not make an existing out-of-format value unopenable/reset it.
    # Strict validation belongs to Save as / Update, not reading the controls.
    return result


def apply(dialog, snapshot):
    """Only supported, present domains apply. Never call the whole Misc save."""
    conf = _ensure_classic_speech_section()
    if 'verbosity' in snapshot:
        data = domains.validate('verbosity', snapshot['verbosity'])
        panel = dialog.verbosityPanel
        panel.get_working_profile_config()
        for name, row in data['profiles'].items():
            panel.workingProfiles[name]['enabledTokens'].update(row['enabledTokens'])
            panel.workingBehaviors[name].update({k: row[k] for k in ('positionMode', 'readEditFieldContents')})
        active = data['defaultProfile']
        panel.currentEditProfile = active
        panel.profileConfig = copy.deepcopy(panel.workingProfiles[active])
        panel.profileBehavior = copy.deepcopy(panel.workingBehaviors[active])
        panel.activeProfileChoice.SetSelection(domains.PROFILE_NAMES.index(active))
        panel._loadEditorsFromProfileConfig()
        panel.apply_live(save=False)
    if 'menus' in snapshot:
        data = domains.validate('menus', snapshot['menus'])
        for key, default in domains.MENU_DEFAULTS.items():
            conf[key] = data[key]
            control = getattr(dialog.menusPanel, key)
            if type(default) is bool:
                control.SetValue(data[key])
            else:
                # SetValue emits EVT_TEXT and can replay other stale rows mid-load.
                control.ChangeValue(data[key])
        dialog.menusPanel._syncMessageAvailability()
    if 'hotkeys' in snapshot:
        data = domains.validate('hotkeys', snapshot['hotkeys'])
        panel = dialog.hotkeysPanel
        panel.hotkeyMode = data['mode']
        panel.hotkeyFormat = data['format']
        panel.hotkeyTypes = data['types']
        panel.dialogAccessKeyOnly = data['dialogAccessKeyOnly']
        panel._loadControlsFromConfig()
        panel._syncDependentControlsAvailability()
        panel.apply_live(save=False)
    if 'keyLabels' in snapshot:
        data = domains.validate('keyLabels', snapshot['keyLabels'])
        data = {k: data[k] for k in ('renames', 'mutedLabels')}
        panel = dialog.keyLabelsPanel
        panel.keyLabelConfig = copy.deepcopy(data)
        panel._loadEditorsFromConfig()
        _save_key_label_config(data)
        _preview_key_label_config(data)
    if 'misc' in snapshot:
        data = domains.validate('misc', snapshot['misc'])
        for key in domains.MISC_DEFAULTS:
            getattr(dialog.miscPanel, key).SetValue(data[key])
        _set_default_button_enabled(data['announceDefaultButton'])
        _set_include_window_state_in_title(data['includeWindowStateInTitle'])
