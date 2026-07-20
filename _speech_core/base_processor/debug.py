"""Shared debug logging gate for ClassicSpeech base processors."""
from __future__ import annotations

import logging

import config
import logHandler


def _classic_speech_debug_enabled() -> bool:
	try:
		try:
			base_conf = config.conf.profiles[0]
		except Exception:
			base_conf = config.conf
		return bool(base_conf.get("classicSpeech", {}).get("debugLogging", False))
	except Exception:
		return False


def _nvda_debug_logging_enabled() -> bool:
	log = logHandler.log
	try:
		is_enabled_for = getattr(log, "isEnabledFor", None)
		if callable(is_enabled_for) and is_enabled_for(logging.DEBUG):
			return True
	except Exception:
		pass
	try:
		get_effective_level = getattr(log, "getEffectiveLevel", None)
		if callable(get_effective_level):
			return int(get_effective_level()) <= logging.DEBUG
	except Exception:
		pass
	return False


def should_debug_log() -> bool:
	"""Return True when base-processor diagnostic logging should emit."""
	return _classic_speech_debug_enabled() or _nvda_debug_logging_enabled()
