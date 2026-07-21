"""Advanced panel settings helpers."""

import logHandler

from .config_core import _ensure_classic_speech_section, _get_running_classic_speech_plugin

log = logHandler.log


def _get_speech_hook_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("speechHookEnabled", True))


def get_speech_hook_enabled():
	return _get_speech_hook_enabled()


def _set_speech_hook_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	enabled = bool(enabled)
	conf["speechHookEnabled"] = enabled
	plugin = _get_running_classic_speech_plugin()
	if plugin is not None and hasattr(plugin, "set_speech_hook_enabled"):
		try:
			plugin.set_speech_hook_enabled(enabled)
		except Exception:
			log.exception("ClassicSpeech: failed to live-apply speech hook setting")
	return enabled


def _get_announce_speech_hook_loaded_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("announceSpeechHookLoaded", False))


def get_announce_speech_hook_loaded_enabled():
	return _get_announce_speech_hook_loaded_enabled()


def _set_announce_speech_hook_loaded_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["announceSpeechHookLoaded"] = bool(enabled)
	return bool(enabled)


def _get_speech_hook_loaded_message():
	conf = _ensure_classic_speech_section()
	message = str(conf.get("speechHookLoadedMessage", "ClassicSpeech hook loaded") or "").strip()
	return message or "ClassicSpeech hook loaded"


def get_speech_hook_loaded_message():
	return _get_speech_hook_loaded_message()


def _set_speech_hook_loaded_message(message: str):
	conf = _ensure_classic_speech_section()
	message = str(message or "").strip()
	conf["speechHookLoadedMessage"] = message
	return message


def _get_gecko_initial_busy_state_presentation_suppressed():
	"""Return the explicit opt-in state for the Firefox Busy experiment."""
	conf = _ensure_classic_speech_section()
	return conf.get("suppressGeckoInitialBusyStatePresentation", False) is True


def get_gecko_initial_busy_state_presentation_suppressed():
	return _get_gecko_initial_busy_state_presentation_suppressed()


def _set_gecko_initial_busy_state_presentation_suppressed(enabled: bool):
	conf = _ensure_classic_speech_section()
	enabled = enabled is True
	conf["suppressGeckoInitialBusyStatePresentation"] = enabled
	plugin = _get_running_classic_speech_plugin()
	if plugin is not None and hasattr(plugin, "set_gecko_initial_busy_state_presentation_suppressed"):
		try:
			plugin.set_gecko_initial_busy_state_presentation_suppressed(enabled)
		except Exception:
			log.exception("ClassicSpeech: failed to live-apply Firefox Busy experiment setting")
	return enabled


def _get_debug_logging_enabled():
	conf = _ensure_classic_speech_section()
	return bool(conf.get("debugLogging", False))


def get_debug_logging_enabled():
	return _get_debug_logging_enabled()


def _set_debug_logging_enabled(enabled: bool):
	conf = _ensure_classic_speech_section()
	conf["debugLogging"] = bool(enabled)
	return bool(enabled)


