# _speech_core/maps.py
"""
Role/state spoken-label maps for Classic Speech.

This version does two separate passes for states:
1. Harvest all positive spoken labels from NVDA's internal _stateLabels table.
2. Harvest all negative spoken labels from NVDA's internal _negativeStateLabels table.

Then, for any State enum members that still have no spoken label entry at all,
we add a conservative fallback based on the enum name so the full semantic state
set is available to the addon.
"""

import re
import logHandler
import controlTypes
from controlTypes import role as ctRoleModule
from controlTypes import state as ctStateModule

log = logHandler.log


def _norm(text):
    if text is None:
        return ""
    return str(text).strip().lower()


def _enum_name_to_label(name):
    return re.sub(r"_+", " ", str(name).strip().lower())


FALLBACK_ROLE_MAP = {
    "button": "button",
    "combo box": "combobox",
    "check box": "checkbox",
    "radio button": "radiobutton",
    "menu item": "menuitem",
    "edit": "edit",
    "text": "statictext",
}

FALLBACK_STATE_MAP = {
    "collapsed": "collapsed",
    "expanded": "expanded",
    "checked": "checked",
    "not checked": "checked",
    "half checked": "halfchecked",
    "partially checked": "halfchecked",
    "pressed": "pressed",
    "not pressed": "pressed",
    "selected": "selected",
    "not selected": "selected",
    "on": "on",
    "off": "on",
    "indeterminate": "indeterminate",
    "has aria details": "has_aria_details",
}

CUSTOM_ROLE_MAP = {
    "edit combo": "editcombo",
}
ROLE_LABEL_ALIASES = {
    "editable combo": "edit combo",
    "editablecombo": "edit combo",
}
CUSTOM_STATE_MAP = {}


def _get_nvda_role_map():
    role_map = {}
    try:
        role_labels = getattr(ctRoleModule, "_roleLabels", {})
        for role in controlTypes.Role:
            label = _norm(role_labels.get(role))
            if not label:
                continue
            role_map[label] = role.name.lower()
    except Exception as e:
        log.debug(f"Role introspection failed: {e}")
        return {}
    return role_map


def _get_nvda_state_map():
    state_map = {}
    try:
        positive_labels = getattr(ctStateModule, "_stateLabels", {})
        negative_labels = getattr(ctStateModule, "_negativeStateLabels", {})

        # Pass 1: positive spoken labels actually defined by NVDA.
        for state in controlTypes.State:
            positive = _norm(positive_labels.get(state))
            if positive:
                state_map[positive] = state.name.lower()

        # Pass 2: negative spoken labels actually defined by NVDA.
        for state in controlTypes.State:
            negative = _norm(negative_labels.get(state))
            if negative:
                state_map[negative] = state.name.lower()

        # Compatibility alias used in older notes / experiments.
        if "half checked" in state_map and "partially checked" not in state_map:
            state_map["partially checked"] = state_map["half checked"]

        # Final pass: ensure every State enum member is addressable, even if NVDA
        # does not define a spoken label for it.
        for state in controlTypes.State:
            semantic = state.name.lower()
            if semantic not in state_map.values():
                fallback_label = _enum_name_to_label(state.name)
                if fallback_label and fallback_label not in state_map:
                    state_map[fallback_label] = semantic
    except Exception as e:
        log.debug(f"State introspection failed: {e}")
        return {}
    return state_map


ROLE_MAP = _get_nvda_role_map() or FALLBACK_ROLE_MAP
STATE_MAP = _get_nvda_state_map() or FALLBACK_STATE_MAP

ROLE_MAP = {**ROLE_MAP, **CUSTOM_ROLE_MAP}
STATE_MAP = {**STATE_MAP, **CUSTOM_STATE_MAP}

SPOKEN_TO_ROLE = ROLE_MAP.copy()
SPOKEN_TO_STATE = STATE_MAP.copy()

ALL_SPOKEN_ROLES_LOWER = set(SPOKEN_TO_ROLE.keys()) | set(ROLE_LABEL_ALIASES.keys())
ALL_SPOKEN_STATES_LOWER = set(SPOKEN_TO_STATE.keys())

log.info(f"Loaded {len(SPOKEN_TO_ROLE)} roles and {len(SPOKEN_TO_STATE)} states")
log.debug(f"ClassicSpeech state spoken keys: {sorted(STATE_MAP.keys())}")
