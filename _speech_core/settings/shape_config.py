"""Shape and speech timing settings helpers."""

import copy
import logHandler

from .config_core import _ensure_classic_speech_section, _get_live_verbosity_manager
from .constants import (
	PAUSE_MODE_GLOBAL,
	PAUSE_PLACEMENT_BEFORE,
	TOKEN_ORDER_KINDS,
	TOKEN_PAUSE_USE_GLOBAL,
)

log = logHandler.log


def _clone_shape_from_manager():
	verbosity = _get_live_verbosity_manager()
	if verbosity is not None:
		try:
			if hasattr(verbosity, "get_shape_config"):
				return verbosity.get_shape_config()
		except Exception:
			log.exception("ClassicSpeech: failed to clone shape config from manager")

	return {
		"pauseMode": PAUSE_MODE_GLOBAL,
		"globalPause": 80,
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


def _preview_shape_config(shape_config: dict):
	verbosity = _get_live_verbosity_manager()
	if verbosity is None:
		return

	try:
		if hasattr(verbosity, "set_shape_config"):
			verbosity.set_shape_config(copy.deepcopy(shape_config), save=False)
	except Exception:
		log.exception("ClassicSpeech: failed to preview shape config")


def _save_shape_config(shape_config: dict):
	verbosity = _get_live_verbosity_manager()
	if verbosity is not None and hasattr(verbosity, "set_shape_config"):
		verbosity.set_shape_config(copy.deepcopy(shape_config), save=True)
		return

	conf = _ensure_classic_speech_section()
	if "shapeData" not in conf:
		conf["shapeData"] = {}
	shape = conf["shapeData"]

	shape["pauseMode"] = str(shape_config.get("pauseMode", PAUSE_MODE_GLOBAL))
	shape["globalPause"] = int(shape_config.get("globalPause", 80))
	shape["order"] = list(shape_config.get("order", []))
	shape["mutedLabels"] = list(shape_config.get("mutedLabels", []))
	shape["pauseAfterFinalToken"] = bool(shape_config.get("pauseAfterFinalToken", True))
	shape["pausePlacement"] = str(shape_config.get("pausePlacement", PAUSE_PLACEMENT_BEFORE))

	shape["renames"] = dict(shape_config.get("renames", {}))
	shape["pauses"] = {
		key: int(value)
		for key, value in dict(shape_config.get("pauses", {})).items()
	}


def _preview_token_shape_edits(renames: dict, muted_labels):
	verbosity = _get_live_verbosity_manager()
	if verbosity is None:
		return

	try:
		shape = _clone_shape_from_manager()
		shape["renames"] = dict(renames or {})
		shape["mutedLabels"] = list(muted_labels or [])
		if hasattr(verbosity, "set_shape_config"):
			verbosity.set_shape_config(shape, save=False)
	except Exception:
		log.exception("ClassicSpeech: failed to preview token shape edits")


def _save_token_shape_edits(renames: dict, muted_labels):
	shape = _clone_shape_from_manager()
	shape["renames"] = dict(renames or {})
	shape["mutedLabels"] = list(muted_labels or [])
	_save_shape_config(shape)


