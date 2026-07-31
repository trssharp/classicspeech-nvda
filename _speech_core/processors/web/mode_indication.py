"""Custom speech for NVDA Browse and Focus Mode indication when sound is off."""
from __future__ import annotations

import functools

import config
import ui

_MARKER = "_classicSpeechModeIndicationRoute"


def _audio_indication_enabled() -> bool:
	try:
		return bool(config.conf["virtualBuffers"]["passThroughAudioIndication"])
	except Exception:
		# Any uncertainty retains NVDA's native reporter.
		return True


def _custom_message(getter) -> str | None:
	try:
		message = getter()
	except Exception:
		return None
	if not isinstance(message, str):
		return None
	message = message.strip()
	return message or None


def install(plugin, *, get_browse_mode_message, get_focus_mode_message):
	"""Install the narrowly scoped reporter wrapper, failing closed to NVDA."""
	try:
		import browseMode

		existing = getattr(browseMode, _MARKER, None)
		if existing:
			owner, _original, wrapper = existing
			if owner is plugin and getattr(browseMode, "reportPassThrough", None) is wrapper:
				return existing
			return None

		original = browseMode.reportPassThrough
		if not callable(original) or not hasattr(original, "last"):
			return None

		@functools.wraps(original)
		def wrapped(treeInterceptor, onlyIfChanged=True):
			# Retain the exact native audio path. With no custom text stored, retain
			# NVDA's localized native speech path as well.
			if _audio_indication_enabled():
				return original(treeInterceptor, onlyIfChanged)
			message = _custom_message(
				get_focus_mode_message if getattr(treeInterceptor, "passThrough", False) else get_browse_mode_message
			)
			if message is None:
				return original(treeInterceptor, onlyIfChanged)
			try:
				if not onlyIfChanged or treeInterceptor.passThrough != original.last:
					ui.message(message)
				original.last = treeInterceptor.passThrough
			except Exception:
				return original(treeInterceptor, onlyIfChanged)

		browseMode.reportPassThrough = wrapped
		setattr(browseMode, _MARKER, (plugin, original, wrapped))
		return (browseMode, original, wrapped)
	except Exception:
		return None


def restore(plugin, record) -> None:
	"""Restore only a wrapper still owned by this plugin instance."""
	if not record:
		return
	try:
		browse_mode, original, wrapper = record
		marker = getattr(browse_mode, _MARKER, None)
		if marker and marker[0] is plugin:
			if getattr(browse_mode, "reportPassThrough", None) is wrapper:
				browse_mode.reportPassThrough = original
			delattr(browse_mode, _MARKER)
	except Exception:
		pass
