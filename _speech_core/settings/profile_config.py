"""Verbosity profile settings helpers."""

import copy
import logHandler

from .config_core import (
	_ensure_classic_speech_section,
	_get_live_verbosity_manager,
	_get_nvda_setting,
	_set_nvda_setting,
)
from .constants import (
	PAUSE_PLACEMENT_BEFORE,
	POSITION_MODE_EACH,
	POSITION_MODE_FIRST,
	POSITION_MODE_OFF,
	TOKEN_PAUSE_USE_GLOBAL,
)

log = logHandler.log


def _get_active_profile_name():
	conf = _ensure_classic_speech_section()
	return conf.get("defaultProfile", "Beginner")


def _set_active_profile_name(profile_name: str):
	conf = _ensure_classic_speech_section()
	conf["defaultProfile"] = profile_name


def _clone_profile_from_manager(profile_name: str):
	verbosity = _get_live_verbosity_manager()
	if verbosity is not None:
		try:
			if hasattr(verbosity, "get_profile_config_for"):
				return verbosity.get_profile_config_for(profile_name)
			if (
				hasattr(verbosity, "get_profile_config")
				and getattr(verbosity, "current_profile", None) == profile_name
			):
				return verbosity.get_profile_config()
		except Exception:
			log.exception("ClassicSpeech: failed to clone profile from manager")

	return {
		"enabledTokens": {
			"name": True,
			"role": True,
			"value": True,
			"state": True,
			"position": True,
			"description": True,
			"tooltip": False,
			"hotkey": True,
		},
		"order": ["name", "role", "value", "state", "position", "description", "hotkey"],
		"pauses": {
			"name": TOKEN_PAUSE_USE_GLOBAL,
			"role": TOKEN_PAUSE_USE_GLOBAL,
			"value": TOKEN_PAUSE_USE_GLOBAL,
			"state": TOKEN_PAUSE_USE_GLOBAL,
			"position": TOKEN_PAUSE_USE_GLOBAL,
			"description": TOKEN_PAUSE_USE_GLOBAL,
			"hotkey": TOKEN_PAUSE_USE_GLOBAL,
		},
		"renames": {},
		"mutedLabels": [],
		"pauseAfterFinalToken": True,
		"pausePlacement": PAUSE_PLACEMENT_BEFORE,
	}



def _preview_profile_config(profile_name: str, profile_config: dict):
	verbosity = _get_live_verbosity_manager()
	if verbosity is None:
		return

	try:
		if hasattr(verbosity, "set_profile_config_for"):
			verbosity.set_profile_config_for(
				profile_name,
				copy.deepcopy(profile_config),
				save=False,
			)
	except Exception:
		log.exception("ClassicSpeech: failed to preview profile config")


def _save_profile_config(profile_name: str, profile_config: dict):
	verbosity = _get_live_verbosity_manager()
	if verbosity is not None and hasattr(verbosity, "set_profile_config_for"):
		verbosity.set_profile_config_for(profile_name, copy.deepcopy(profile_config), save=True)
		return

	conf = _ensure_classic_speech_section()
	profileData = conf["profileData"]
	if profile_name not in profileData:
		profileData[profile_name] = {}
	section = profileData[profile_name]
	enabled = copy.deepcopy(profile_config.get("enabledTokens", {}))
	enabled.pop("value", None)
	if "enabledTokens" not in section or not hasattr(section.get("enabledTokens", {}), "keys"):
		section["enabledTokens"] = {}
	enabledSection = section["enabledTokens"]
	for key in list(enabledSection.keys()):
		if key not in enabled:
			try:
				del enabledSection[key]
			except Exception:
				pass
	for key, value in enabled.items():
		enabledSection[key] = bool(value)


def _clear_profile_override(profile_name: str):
	verbosity = _get_live_verbosity_manager()
	if verbosity is not None and hasattr(verbosity, "reset_profile_config_for"):
		verbosity.reset_profile_config_for(profile_name, save=True)
		return

	conf = _ensure_classic_speech_section()
	profileData = conf.get("profileData", {})
	try:
		if profile_name in profileData:
			profileData[profile_name] = {}
	except Exception:
		pass


def _apply_profile_live(profile_name: str):
	verbosity = _get_live_verbosity_manager()
	if verbosity is None:
		return

	try:
		if hasattr(verbosity, "set_profile"):
			verbosity.set_profile(profile_name)
		else:
			verbosity.current_profile = profile_name
			if hasattr(verbosity, "load_from_config"):
				verbosity.load_from_config()
		log.info(f"ClassicSpeech: live-applied profile {profile_name}")
	except Exception:
		log.exception(f"ClassicSpeech: failed to live-apply profile {profile_name}")


def _apply_profile_live_if_active(profile_name: str):
	active = _get_active_profile_name()
	if active != profile_name:
		return
	_apply_profile_live(profile_name)


PROFILE_POSITION_DEFAULTS = {
	"Beginner": POSITION_MODE_EACH,
	"Intermediate": POSITION_MODE_FIRST,
	"Advanced": POSITION_MODE_OFF,
}


def _default_profile_behavior(profile_name: str = "Beginner"):
	return {
		"positionMode": PROFILE_POSITION_DEFAULTS.get(
			profile_name,
			POSITION_MODE_EACH,
		),
	}


def _get_profile_behavior(profile_name: str):
	conf = _ensure_classic_speech_section()
	behaviorData = conf.get("profileBehaviorData", {})
	section = behaviorData.get(profile_name, {})

	if hasattr(section, "dict"):
		section = section.dict()
	elif not isinstance(section, dict):
		try:
			section = dict(section)
		except Exception:
			section = {}

	result = _default_profile_behavior(profile_name)
	if "positionMode" in section:
		mode = str(section.get("positionMode", POSITION_MODE_EACH))
		if mode in {POSITION_MODE_OFF, POSITION_MODE_FIRST, POSITION_MODE_EACH}:
			result["positionMode"] = mode
	elif "speakPositionOnMove" in section:
		result["positionMode"] = (
			POSITION_MODE_EACH
			if bool(section.get("speakPositionOnMove"))
			else POSITION_MODE_FIRST
		)
	else:
		try:
			if not bool(_get_nvda_setting("presentation", "reportObjectPositionInformation", True)):
				result["positionMode"] = POSITION_MODE_OFF
		except Exception:
			pass

	return result


def _save_profile_behavior(profile_name: str, behavior: dict):
	conf = _ensure_classic_speech_section()
	behaviorData = conf["profileBehaviorData"]
	if profile_name not in behaviorData:
		behaviorData[profile_name] = {}
	section = behaviorData[profile_name]
	mode = str(behavior.get("positionMode", POSITION_MODE_EACH))
	if mode not in {POSITION_MODE_OFF, POSITION_MODE_FIRST, POSITION_MODE_EACH}:
		mode = POSITION_MODE_EACH
	section["positionMode"] = mode


def _clear_profile_behavior_override(profile_name: str):
	conf = _ensure_classic_speech_section()
	behaviorData = conf.get("profileBehaviorData", {})
	try:
		if profile_name in behaviorData:
			behaviorData[profile_name] = {}
	except Exception:
		pass


def _apply_profile_behavior_runtime(profile_config: dict, behavior: dict):
	enabled = profile_config.get("enabledTokens", {})

	speak_description = bool(enabled.get("description", True))
	_set_nvda_setting(
		"presentation",
		"reportObjectDescriptions",
		speak_description,
	)

	speak_tooltip = bool(enabled.get("tooltip", False))
	_set_nvda_setting(
		"presentation",
		"reportTooltips",
		speak_tooltip,
	)

	mode = str(behavior.get("positionMode", POSITION_MODE_EACH))
	if mode not in {POSITION_MODE_OFF, POSITION_MODE_FIRST, POSITION_MODE_EACH}:
		mode = POSITION_MODE_EACH

	speak_position = mode != POSITION_MODE_OFF
	_set_nvda_setting(
		"presentation",
		"reportObjectPositionInformation",
		speak_position,
	)

	conf = _ensure_classic_speech_section()
	conf["positionMode"] = mode
