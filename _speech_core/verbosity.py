# _speech_core/verbosity.py
import config
import logHandler

from .settings import (
    POSITION_MODE_EACH,
    POSITION_MODE_FIRST,
    POSITION_MODE_OFF,
)

from .tokens import (
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_TOOLTIP,
    TOKEN_ROLE,
    TOKEN_STATE,
    TOKEN_VALUE,
)

log = logHandler.log


DEFAULT_TOKEN_ORDER = [
    TOKEN_NAME,
    TOKEN_ROLE,
    TOKEN_VALUE,
    TOKEN_STATE,
    TOKEN_POSITION,
    TOKEN_DESCRIPTION,
    TOKEN_HOTKEY,
]

DEFAULT_PAUSES = {
    TOKEN_NAME: -1,
    TOKEN_ROLE: -1,
    TOKEN_VALUE: -1,
    TOKEN_STATE: -1,
    TOKEN_POSITION: -1,
    TOKEN_DESCRIPTION: -1,
    TOKEN_HOTKEY: -1,
}

PAUSE_MODE_GLOBAL = "global"
PAUSE_MODE_PER_TOKEN = "perToken"
PAUSE_PLACEMENT_AFTER = "after"
PAUSE_PLACEMENT_BEFORE = "before"

DEFAULT_GLOBAL_PAUSE = 80
DEFAULT_PAUSE_AFTER_FINAL_TOKEN = True
DEFAULT_PAUSE_PLACEMENT = PAUSE_PLACEMENT_BEFORE


def _default_enabled_tokens():
    return {
        TOKEN_NAME: True,
        TOKEN_ROLE: True,
        TOKEN_VALUE: True,
        TOKEN_STATE: True,
        TOKEN_POSITION: True,
        TOKEN_DESCRIPTION: True,
        TOKEN_TOOLTIP: False,
        TOKEN_HOTKEY: True,
    }


def _profile(*, enabled=None):
    return {
        "enabledTokens": (
            dict(enabled) if enabled is not None else _default_enabled_tokens()
        ),
    }


def _shape(
    *,
    pauseMode=PAUSE_MODE_GLOBAL,
    globalPause=DEFAULT_GLOBAL_PAUSE,
    order=None,
    renames=None,
    mutedLabels=None,
    pauses=None,
    pauseAfterFinalToken=DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
    pausePlacement=DEFAULT_PAUSE_PLACEMENT,
):
    return {
        "pauseMode": str(pauseMode or PAUSE_MODE_GLOBAL),
        "globalPause": int(globalPause),
        "order": list(order) if order is not None else list(DEFAULT_TOKEN_ORDER),
        "renames": dict(renames) if renames is not None else {},
        "mutedLabels": list(mutedLabels) if mutedLabels is not None else [],
        "pauses": dict(pauses) if pauses is not None else dict(DEFAULT_PAUSES),
        "pauseAfterFinalToken": bool(pauseAfterFinalToken),
        "pausePlacement": str(pausePlacement or DEFAULT_PAUSE_PLACEMENT),
    }


class VerbosityManager:
    """
    Canonical owner of speech verbosity profile selection and config persistence.

    Ownership:
    - profile config owns "how much speech" (enabled token categories)
    - global shape config owns "how speech is shaped" (order, renames, mutedLabels, pauses)

    Pause model:
    - current UI uses a single global pause
    - per-token pauses remain supported in the backend for future hybrid UI
    """

    PROFILES = {
        "Beginner": _profile(
            enabled={
                TOKEN_NAME: True,
                TOKEN_ROLE: True,
                TOKEN_VALUE: True,
                TOKEN_STATE: True,
                TOKEN_POSITION: True,
                TOKEN_DESCRIPTION: True,
                TOKEN_TOOLTIP: False,
                TOKEN_HOTKEY: True,
            },
        ),
        "Intermediate": _profile(
            enabled={
                TOKEN_NAME: True,
                TOKEN_ROLE: True,
                TOKEN_VALUE: True,
                TOKEN_STATE: True,
                TOKEN_POSITION: True,
                TOKEN_DESCRIPTION: True,
                TOKEN_TOOLTIP: False,
                TOKEN_HOTKEY: True,
            },
        ),
        "Advanced": _profile(
            enabled={
                TOKEN_NAME: True,
                TOKEN_ROLE: False,
                TOKEN_VALUE: True,
                TOKEN_STATE: True,
                TOKEN_POSITION: False,
                TOKEN_DESCRIPTION: False,
                TOKEN_TOOLTIP: False,
                TOKEN_HOTKEY: False,
            },
        ),
    }

    DEFAULT_SHAPE = _shape()

    TOKEN_TO_LEGACY_KEY = {
        TOKEN_NAME: "speak_name",
        TOKEN_ROLE: "speak_role",
        TOKEN_STATE: "speak_state",
        TOKEN_POSITION: "speak_position",
        TOKEN_DESCRIPTION: "speak_description",
        TOKEN_TOOLTIP: "speak_tooltip",
        TOKEN_HOTKEY: "speak_hotkey",
    }

    LEGACY_KEY_TO_TOKEN = {v: k for k, v in TOKEN_TO_LEGACY_KEY.items()}

    def __init__(self):
        self.current_profile = "Beginner"
        self.profile_data = self._clone_profile(self.PROFILES["Beginner"])
        self.shape_data = self._clone_shape(self.DEFAULT_SHAPE)

        self.announce_default_button = False

        self.load_from_config()

    def _config_section(self):
        if "classicSpeech" not in config.conf:
            config.conf["classicSpeech"] = {}
        conf = config.conf["classicSpeech"]

        if "profileData" not in conf:
            conf["profileData"] = {}
        if "shapeData" not in conf:
            conf["shapeData"] = {}

        return conf

    def _clone_profile(self, profile_dict):
        return {
            "enabledTokens": dict(profile_dict.get("enabledTokens", {})),
        }

    def _clone_shape(self, shape_dict):
        return {
            "pauseMode": str(shape_dict.get("pauseMode", PAUSE_MODE_GLOBAL)),
            "globalPause": int(shape_dict.get("globalPause", DEFAULT_GLOBAL_PAUSE)),
            "order": list(shape_dict.get("order", DEFAULT_TOKEN_ORDER)),
            "renames": dict(shape_dict.get("renames", {})),
            "mutedLabels": list(shape_dict.get("mutedLabels", [])),
            "pauses": dict(shape_dict.get("pauses", DEFAULT_PAUSES)),
            "pausePlacement": str(shape_dict.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT)),
            "pauseAfterFinalToken": bool(
                shape_dict.get(
                    "pauseAfterFinalToken",
                    DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
                )
            ),
        }

    def _normalize_profile(self, profile_dict):
        base = self._clone_profile(_profile())

        if not isinstance(profile_dict, dict):
            return base

        enabled = profile_dict.get("enabledTokens", {})
        if isinstance(enabled, dict):
            for key, value in enabled.items():
                if key in base["enabledTokens"]:
                    base["enabledTokens"][key] = bool(value)

        base["enabledTokens"][TOKEN_POSITION] = True
        base["enabledTokens"][TOKEN_VALUE] = True
        # Hotkeys are owned by the Hotkeys panel, not by verbosity profiles.
        # Keep the token enabled so formatter can speak hotkeys after the
        # processor-level mode has decided whether they belong in the sequence.
        base["enabledTokens"][TOKEN_HOTKEY] = True
        return base

    def _normalize_shape(self, shape_dict):
        base = self._clone_shape(_shape())

        if not isinstance(shape_dict, dict):
            return base

        pauseMode = str(shape_dict.get("pauseMode", PAUSE_MODE_GLOBAL))
        if pauseMode not in {PAUSE_MODE_GLOBAL, PAUSE_MODE_PER_TOKEN}:
            pauseMode = PAUSE_MODE_GLOBAL
        base["pauseMode"] = pauseMode

        try:
            base["globalPause"] = max(0, int(shape_dict.get("globalPause", DEFAULT_GLOBAL_PAUSE)))
        except (TypeError, ValueError):
            base["globalPause"] = DEFAULT_GLOBAL_PAUSE

        order = shape_dict.get("order")
        if isinstance(order, list):
            filtered = [k for k in order if k in DEFAULT_TOKEN_ORDER]
            seen = set(filtered)
            for token_kind in DEFAULT_TOKEN_ORDER:
                if token_kind not in seen:
                    filtered.append(token_kind)
            base["order"] = filtered

        renames = shape_dict.get("renames", {})
        if isinstance(renames, dict):
            clean = {}
            for key, value in renames.items():
                if key is None:
                    continue
                key = str(key).strip()
                value = str(value).strip()
                if key:
                    clean[key] = value
            base["renames"] = clean

        muted = shape_dict.get("mutedLabels", [])
        if isinstance(muted, (list, tuple, set)):
            clean = []
            seen = set()
            for label in muted:
                if label is None:
                    continue
                text = str(label).strip()
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                clean.append(text)
            base["mutedLabels"] = clean

        pauses = shape_dict.get("pauses", {})
        if isinstance(pauses, dict):
            for token_kind, value in pauses.items():
                if token_kind in base["pauses"]:
                    try:
                        base["pauses"][token_kind] = max(-1, int(value))
                    except (TypeError, ValueError):
                        pass

        if "pauseAfterFinalToken" in shape_dict:
            base["pauseAfterFinalToken"] = bool(
                shape_dict.get("pauseAfterFinalToken")
            )

        pausePlacement = str(shape_dict.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT))
        if pausePlacement not in {PAUSE_PLACEMENT_AFTER, PAUSE_PLACEMENT_BEFORE}:
            pausePlacement = DEFAULT_PAUSE_PLACEMENT
        base["pausePlacement"] = pausePlacement

        return base

    def _merge_profile_and_shape(self, profile_dict, shape_dict):
        profile = self._normalize_profile(profile_dict)
        shape = self._normalize_shape(shape_dict)
        return {
            "enabledTokens": dict(profile.get("enabledTokens", {})),
            "pauseMode": shape.get("pauseMode", PAUSE_MODE_GLOBAL),
            "globalPause": int(shape.get("globalPause", DEFAULT_GLOBAL_PAUSE)),
            "order": list(shape.get("order", DEFAULT_TOKEN_ORDER)),
            "renames": dict(shape.get("renames", {})),
            "mutedLabels": list(shape.get("mutedLabels", [])),
            "pauses": dict(shape.get("pauses", DEFAULT_PAUSES)),
            "pausePlacement": str(shape.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT)),
            "pauseAfterFinalToken": bool(
                shape.get("pauseAfterFinalToken", DEFAULT_PAUSE_AFTER_FINAL_TOKEN)
            ),
        }

    def _split_effective_profile_config(self, profile_config):
        if not isinstance(profile_config, dict):
            return self._clone_profile(_profile()), self._clone_shape(_shape())

        profile_part = {
            "enabledTokens": profile_config.get("enabledTokens", {}),
        }
        shape_part = {
            "pauseMode": profile_config.get("pauseMode", PAUSE_MODE_GLOBAL),
            "globalPause": profile_config.get("globalPause", DEFAULT_GLOBAL_PAUSE),
            "order": profile_config.get("order", DEFAULT_TOKEN_ORDER),
            "renames": profile_config.get("renames", {}),
            "mutedLabels": profile_config.get("mutedLabels", []),
            "pauses": profile_config.get("pauses", DEFAULT_PAUSES),
            "pausePlacement": profile_config.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT),
            "pauseAfterFinalToken": profile_config.get(
                "pauseAfterFinalToken",
                DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
            ),
        }
        return (
            self._normalize_profile(profile_part),
            self._normalize_shape(shape_part),
        )

    def _legacy_from_profile(self, profile_dict):
        enabled = profile_dict.get("enabledTokens", {})
        return {
            legacy_key: bool(enabled.get(token_kind, True))
            for token_kind, legacy_key in self.TOKEN_TO_LEGACY_KEY.items()
        }

    def _profile_from_legacy(self, legacy_dict, base_profile=None):
        if base_profile is None:
            profile = self._clone_profile(_profile())
        else:
            profile = self._clone_profile(base_profile)

        enabled = profile["enabledTokens"]
        for legacy_key, value in legacy_dict.items():
            token_kind = self.LEGACY_KEY_TO_TOKEN.get(legacy_key)
            if token_kind is not None:
                enabled[token_kind] = bool(value)

        enabled[TOKEN_POSITION] = True
        enabled[TOKEN_VALUE] = True
        return self._normalize_profile(profile)

    def _read_profile_override(self, profile_name: str):
        conf = self._config_section()
        profileData = conf.get("profileData", {})
        section = profileData.get(profile_name)
        if not section:
            return None

        if hasattr(section, "dict"):
            section = section.dict()
        elif not isinstance(section, dict):
            try:
                section = dict(section)
            except Exception:
                return None

        override = {
            "enabledTokens": {},
        }

        enabledSection = section.get("enabledTokens", {})
        if hasattr(enabledSection, "dict"):
            enabledSection = enabledSection.dict()

        for token_kind in DEFAULT_TOKEN_ORDER:
            if token_kind == TOKEN_VALUE:
                continue
            if token_kind in enabledSection:
                override["enabledTokens"][token_kind] = bool(enabledSection[token_kind])

        override["enabledTokens"][TOKEN_POSITION] = True
        override["enabledTokens"][TOKEN_VALUE] = True
        return override

    def _write_profile_override(self, profile_name: str, profile_config: dict):
        conf = self._config_section()
        profileData = conf["profileData"]

        if profile_name not in profileData:
            profileData[profile_name] = {}
        profileSection = profileData[profile_name]

        normalized = self._normalize_profile(profile_config)

        if "enabledTokens" not in profileSection:
            profileSection["enabledTokens"] = {}
        enabledSection = profileSection["enabledTokens"]

        for token_kind, value in normalized["enabledTokens"].items():
            if token_kind == TOKEN_VALUE:
                continue
            enabledSection[token_kind] = bool(value)

        enabledSection[TOKEN_POSITION] = True

    def _delete_profile_override(self, profile_name: str):
        conf = self._config_section()
        profileData = conf.get("profileData", {})
        try:
            if profile_name in profileData:
                profileData[profile_name] = {}
        except Exception:
            pass

    def _read_shape_override(self):
        conf = self._config_section()
        shapeSection = conf.get("shapeData", {})

        if hasattr(shapeSection, "dict"):
            shapeSection = shapeSection.dict()
        elif not isinstance(shapeSection, dict):
            try:
                shapeSection = dict(shapeSection)
            except Exception:
                shapeSection = {}

        override = {
            "pauseMode": PAUSE_MODE_GLOBAL,
            "globalPause": DEFAULT_GLOBAL_PAUSE,
            "order": DEFAULT_TOKEN_ORDER,
            "renames": {},
            "mutedLabels": [],
            "pauses": DEFAULT_PAUSES,
            "pauseAfterFinalToken": DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
        }

        if "pauseMode" in shapeSection:
            override["pauseMode"] = shapeSection["pauseMode"]
        if "globalPause" in shapeSection:
            override["globalPause"] = shapeSection["globalPause"]
        if "order" in shapeSection:
            override["order"] = list(shapeSection["order"])
        if "renames" in shapeSection:
            override["renames"] = dict(shapeSection["renames"])
        if "mutedLabels" in shapeSection:
            override["mutedLabels"] = list(shapeSection["mutedLabels"])
        if "pauses" in shapeSection:
            override["pauses"] = dict(shapeSection["pauses"])
        if "pauseAfterFinalToken" in shapeSection:
            override["pauseAfterFinalToken"] = bool(shapeSection["pauseAfterFinalToken"])

        return self._normalize_shape(override)

    def _write_shape_override(self, shape_config: dict):
        conf = self._config_section()
        shapeSection = conf["shapeData"]

        normalized = self._normalize_shape(shape_config)

        shapeSection["pauseMode"] = str(normalized["pauseMode"])
        shapeSection["globalPause"] = int(normalized["globalPause"])
        shapeSection["order"] = list(normalized["order"])
        shapeSection["mutedLabels"] = list(normalized.get("mutedLabels", []))
        shapeSection["pauseAfterFinalToken"] = bool(
            normalized.get(
                "pauseAfterFinalToken",
                DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
            )
        )

        # Important: clear nested subsections before rewriting them.
        # Otherwise deleted rename/pause entries can linger in the config file
        # across restarts even though the live dialog looks correct.
        shapeSection["renames"] = {}
        renamesSection = shapeSection["renames"]
        for key, value in normalized["renames"].items():
            renamesSection[str(key)] = str(value)

        shapeSection["pauses"] = {}
        pausesSection = shapeSection["pauses"]
        for key, value in normalized["pauses"].items():
            pausesSection[key] = int(value)

    def _delete_shape_override(self):
        conf = self._config_section()
        try:
            conf["shapeData"] = {}
        except Exception:
            pass

    def _build_profile_config(self, profile_name: str):
        base_profile = self._clone_profile(self.PROFILES.get(profile_name, _profile()))
        profile_override = self._read_profile_override(profile_name)
        if isinstance(profile_override, dict):
            merged_profile = self._clone_profile(base_profile)
            merged_profile["enabledTokens"].update(
                profile_override.get("enabledTokens", {})
            )
            base_profile = merged_profile

        base_profile["enabledTokens"][TOKEN_POSITION] = True
        return self._normalize_profile(base_profile)

    def _build_shape_config(self):
        override = self._read_shape_override()
        base = self._clone_shape(self.DEFAULT_SHAPE)

        if isinstance(override, dict):
            merged = self._clone_shape(base)
            merged["pauseMode"] = override.get("pauseMode", PAUSE_MODE_GLOBAL)
            merged["globalPause"] = override.get("globalPause", DEFAULT_GLOBAL_PAUSE)
            if isinstance(override.get("order"), list) and override["order"]:
                merged["order"] = list(override["order"])
            merged["renames"].update(override.get("renames", {}))
            merged["mutedLabels"] = list(override.get("mutedLabels", []))
            merged["pauses"].update(override.get("pauses", {}))
            if "pauseAfterFinalToken" in override:
                merged["pauseAfterFinalToken"] = bool(
                    override.get(
                        "pauseAfterFinalToken",
                        DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
                    )
                )
            base = merged

        return self._normalize_shape(base)

    def load_from_config(self):
        conf = self._config_section()

        saved_profile = conf.get("defaultProfile", "Beginner")
        if saved_profile not in self.PROFILES:
            saved_profile = "Beginner"

        self.current_profile = saved_profile
        self.profile_data = self._build_profile_config(saved_profile)
        self.shape_data = self._build_shape_config()

        self.announce_default_button = conf.get("announceDefaultButton", False)

        log.info(f"VerbosityManager loaded profile: {self.current_profile}")

    def save_profile_data(self):
        self._write_profile_override(self.current_profile, self.profile_data)
        self._write_shape_override(self.shape_data)
        self._config_section()["defaultProfile"] = self.current_profile

    def set_profile(self, profile_name: str):
        if profile_name not in self.PROFILES:
            log.error(f"ClassicSpeech: Unknown profile '{profile_name}'")
            return

        self.current_profile = profile_name
        self._config_section()["defaultProfile"] = profile_name
        self.profile_data = self._build_profile_config(profile_name)
        log.info(f"ClassicSpeech: Switched to {profile_name} verbosity profile")

    def get_profile_config(self):
        return self._merge_profile_and_shape(self.profile_data, self.shape_data)

    def get_profile_config_for(self, profile_name: str):
        profile = self._build_profile_config(profile_name)
        return self._merge_profile_and_shape(profile, self.shape_data)

    def get_query_profile_config(self):
        """
        Query speech is always Beginner verbosity with value forced on.
        Shape settings remain unchanged.
        """
        profile = self._build_profile_config("Beginner")
        profile["enabledTokens"][TOKEN_VALUE] = True
        return self._merge_profile_and_shape(profile, self.shape_data)

    def get_query_behavior(self):
        """
        Query behavior should not leak the currently active profile's runtime
        hotkey/position gating. Use Beginner's saved behavior for position, and
        allow remembered hotkeys through whenever Beginner has hotkeys enabled.
        """
        conf = self._config_section()
        behavior_data = conf.get("profileBehaviorData", {})
        section = behavior_data.get("Beginner", {})
        if hasattr(section, "dict"):
            section = section.dict()
        elif not isinstance(section, dict):
            try:
                section = dict(section)
            except Exception:
                section = {}

        position_mode = POSITION_MODE_EACH
        mode = str(section.get("positionMode", POSITION_MODE_EACH)).strip().lower()
        if mode in {POSITION_MODE_OFF, POSITION_MODE_FIRST, POSITION_MODE_EACH}:
            position_mode = mode
        else:
            try:
                if not bool(config.conf["presentation"].get("reportObjectPositionInformation", True)):
                    position_mode = POSITION_MODE_OFF
            except Exception:
                position_mode = POSITION_MODE_EACH

        profile = self._build_profile_config("Beginner")
        profile["enabledTokens"][TOKEN_VALUE] = True
        allow_hotkey = bool(profile.get("enabledTokens", {}).get(TOKEN_HOTKEY, True))

        return {
            "positionMode": position_mode,
            "allowHotkey": allow_hotkey,
        }

    def set_profile_config(self, profile_config: dict, save=True):
        profile_part, shape_part = self._split_effective_profile_config(profile_config)
        self.profile_data = profile_part
        self.shape_data = shape_part
        if save:
            self.save_profile_data()

    def set_profile_config_for(self, profile_name: str, profile_config: dict, save=True):
        profile_part, shape_part = self._split_effective_profile_config(profile_config)

        if save:
            self._write_profile_override(profile_name, profile_part)
            self._write_shape_override(shape_part)

        self.shape_data = self._clone_shape(shape_part)

        if self.current_profile == profile_name:
            self.profile_data = self._clone_profile(profile_part)

    def reset_profile_config_for(self, profile_name: str, save=True):
        if save:
            self._delete_profile_override(profile_name)

        rebuilt_profile = self._build_profile_config(profile_name)
        if self.current_profile == profile_name:
            self.profile_data = self._clone_profile(rebuilt_profile)

        return self._merge_profile_and_shape(rebuilt_profile, self.shape_data)

    def get_shape_config(self):
        return self._clone_shape(self.shape_data)

    def set_shape_config(self, shape_config: dict, save=True):
        self.shape_data = self._normalize_shape(shape_config)
        if save:
            self.save_profile_data()

    def reset_shape_config(self, save=True):
        if save:
            self._delete_shape_override()
        self.shape_data = self._build_shape_config()
        return self.get_shape_config()

    def get_global_pause(self):
        return int(self.shape_data.get("globalPause", DEFAULT_GLOBAL_PAUSE))

    def set_global_pause(self, pause_ms, save=True):
        shape = self._clone_shape(self.shape_data)
        try:
            shape["globalPause"] = max(0, int(pause_ms))
        except (TypeError, ValueError):
            shape["globalPause"] = DEFAULT_GLOBAL_PAUSE
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_pause_mode(self):
        return str(self.shape_data.get("pauseMode", PAUSE_MODE_GLOBAL))

    def set_pause_mode(self, mode, save=True):
        shape = self._clone_shape(self.shape_data)
        mode = str(mode or PAUSE_MODE_GLOBAL)
        if mode not in {PAUSE_MODE_GLOBAL, PAUSE_MODE_PER_TOKEN}:
            mode = PAUSE_MODE_GLOBAL
        shape["pauseMode"] = mode
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_verbosity(self):
        return self._legacy_from_profile(self.profile_data)

    def set_verbosity(self, legacy_verbosity: dict, save=True):
        self.profile_data = self._profile_from_legacy(
            legacy_verbosity,
            base_profile=self.profile_data,
        )
        if save:
            self.save_profile_data()

    def get_muted_labels(self):
        return list(self.shape_data.get("mutedLabels", []))

    def set_muted_labels(self, muted_labels, save=True):
        shape = self._clone_shape(self.shape_data)
        shape["mutedLabels"] = list(muted_labels or [])
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_pauses(self):
        return dict(self.shape_data.get("pauses", DEFAULT_PAUSES))

    def set_pauses(self, pauses: dict, save=True):
        shape = self._clone_shape(self.shape_data)
        for token_kind, value in pauses.items():
            if token_kind in shape["pauses"]:
                try:
                    shape["pauses"][token_kind] = max(-1, int(value))
                except (TypeError, ValueError):
                    pass
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_pause_after_final_token(self):
        return bool(
            self.shape_data.get(
                "pauseAfterFinalToken",
                DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
            )
        )

    def set_pause_after_final_token(self, enabled, save=True):
        shape = self._clone_shape(self.shape_data)
        shape["pauseAfterFinalToken"] = bool(enabled)
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_enabled_tokens(self):
        return dict(self.profile_data.get("enabledTokens", {}))

    def set_enabled_tokens(self, enabled_tokens: dict, save=True):
        profile = self._clone_profile(self.profile_data)
        profile["enabledTokens"].update(enabled_tokens)
        profile["enabledTokens"][TOKEN_POSITION] = True
        self.profile_data = self._normalize_profile(profile)
        if save:
            self.save_profile_data()

    def get_token_order(self):
        return list(self.shape_data.get("order", DEFAULT_TOKEN_ORDER))

    def set_token_order(self, order: list, save=True):
        shape = self._clone_shape(self.shape_data)
        shape["order"] = list(order)
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def get_renames(self):
        return dict(self.shape_data.get("renames", {}))

    def set_renames(self, renames: dict, save=True):
        shape = self._clone_shape(self.shape_data)
        shape["renames"] = dict(renames)
        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()

    def rename_spoken_label(self, original_text: str, new_text: str, save=True):
        original_text = str(original_text).strip()
        new_text = str(new_text).strip()
        if not original_text:
            return

        shape = self._clone_shape(self.shape_data)
        renames = shape["renames"]

        if new_text:
            renames[original_text] = new_text
        else:
            renames.pop(original_text, None)

        self.shape_data = self._normalize_shape(shape)
        if save:
            self.save_profile_data()
