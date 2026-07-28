"""Shared ClassicSpeech settings config helpers.

This module intentionally contains only primitives used across multiple
settings panels/config modules. Panel-specific helpers belong in separate
`*_config.py` modules.
"""
import copy

import config
import globalPluginHandler
import logHandler


log = logHandler.log


def _to_plain_data(value):
	if hasattr(value, "dict") and callable(value.dict):
		try:
			value = value.dict()
		except Exception:
			pass

	if isinstance(value, dict):
		return {k: _to_plain_data(v) for k, v in value.items()}

	if isinstance(value, (list, tuple)):
		return [_to_plain_data(v) for v in value]

	try:
		return copy.deepcopy(value)
	except Exception:
		return value


def _normalize_late_registered_boolean_values(section, spec):
	"""Convert ConfigObj's late-schema ``"True"``/``"False"`` leaves safely.

	NVDA may expose values in an add-on section registered after configuration
	loading as strings. Only schema-declared Boolean leaves are converted: custom
	messages and user-provided text are never interpreted as Boolean values.
	"""
	if not hasattr(section, "get") or not hasattr(spec, "items"):
		return
	for key, key_spec in spec.items():
		try:
			value = section.get(key)
		except Exception:
			continue
		if str(key_spec).strip().lower().startswith("boolean("):
			if isinstance(value, str):
				section[key] = value.strip().lower() in {"1", "true", "yes", "on"}
		elif hasattr(key_spec, "items"):
			_normalize_late_registered_boolean_values(value, key_spec)


def _ensure_classic_speech_section():
	"""Return the base ClassicSpeech config section.

	ClassicSpeech registers its top-level section as base-only. Text processing
	settings must read and write that same base section, not a transient layered
	profile view, otherwise the settings panel and speech hook can disagree.
	"""
	try:
		baseConf = config.conf.profiles[0]
	except Exception:
		baseConf = config.conf

	if "classicSpeech" not in baseConf:
		baseConf["classicSpeech"] = {}
	conf = baseConf["classicSpeech"]
	try:
		spec = config.conf.spec.get("classicSpeech", {})
		if not spec:
			from ..plugin_config import _CLASSIC_SPEECH_SPEC
			spec = _CLASSIC_SPEECH_SPEC
		_normalize_late_registered_boolean_values(conf, spec)
	except Exception:
		log.debug("ClassicSpeech: could not normalize late Boolean config values", exc_info=True)

	if "profileData" not in conf:
		conf["profileData"] = {}
	if "profileBehaviorData" not in conf:
		conf["profileBehaviorData"] = {}

	return conf


def _replace_section_contents(section, plain_data: dict):
	try:
		for key in list(section.keys()):
			try:
				del section[key]
			except Exception:
				pass
	except Exception:
		pass

	for key, value in plain_data.items():
		section[key] = copy.deepcopy(value)


def _get_running_classic_speech_plugin():
	try:
		return next(
			(
				p
				for p in globalPluginHandler.runningPlugins
				if p.__class__.__module__.startswith("globalPlugins.classicSpeech")
			),
			None,
		)
	except Exception:
		return None


def _get_live_verbosity_manager():
	plugin = _get_running_classic_speech_plugin()
	if plugin and hasattr(plugin, "processor") and hasattr(plugin.processor, "verbosity"):
		return plugin.processor.verbosity
	return None


def _get_nvda_setting(section: str, key: str, default=False):
	try:
		return bool(config.conf[section][key])
	except Exception:
		return bool(default)


def _set_nvda_setting(section: str, key: str, value):
	try:
		if section not in config.conf:
			config.conf[section] = {}
		config.conf[section][key] = bool(value)
	except Exception:
		log.exception(f"Failed to set NVDA config {section}.{key}")






