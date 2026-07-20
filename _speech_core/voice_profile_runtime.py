"""Choose queue-safe full active-synth Voice Profile triggers when needed."""
from __future__ import annotations

from .voice_profile_overlay import VoiceProfileOverlay
from .voice_profile_trigger import VoiceProfileDirectSettingsTransaction, VoiceProfileOverlayTrigger

_SEQUENCE_SAFE_PROSODY = frozenset(("rate", "pitch", "volume"))


def make_voice_profile_overlay_trigger(profile_id, config_manager, driver, snapshot, profile_factory=None):
	"""Build a queue-bound Preview-equivalent transaction that survives NVDA reload."""
	return VoiceProfileOverlayTrigger(
		profile_id,
		VoiceProfileOverlay(config_manager, str(driver.name), snapshot, profile_factory=profile_factory),
		VoiceProfileDirectSettingsTransaction(driver, snapshot),
	)


def _requires_full_overlay(config_manager, driver, snapshot):
	"""True when any supported saved setting differs from native configuration.

	The queue transaction mirrors Preview: it owns every advertised profile
	setting, including Rate/Pitch/Volume. Keeping numeric-only differences on a
	separate command path would let a complete formatter sequence bypass its
	selected profile when full routing is requested.
	"""
	try:
		configured = config_manager["speech"][str(driver.name)]
		for setting in driver.supportedSettings:
			setting_id = getattr(setting, "id", "")
			if not setting_id or setting_id not in snapshot:
				continue
			value = snapshot[setting_id]
			# Numeric synth settings must remain numeric. Invalid persisted data is
			# ignored rather than being handed to a driver setter at a queue boundary.
			if setting_id in _SEQUENCE_SAFE_PROSODY and (
				isinstance(value, bool) or not isinstance(value, (int, float))
			):
				continue
			if configured.get(setting_id) != value:
				return True
	except Exception:
		return False
	return False


def active_full_profile_trigger(profile_id, snapshot_getter):
	"""Return a trigger only for a non-prosody same-synth route difference.

	``snapshot_getter`` is injected by the prosody router to keep this module free
	of its private registry/storage implementation.
	"""
	try:
		import config
		from synthDriverHandler import getSynth

		driver, snapshot = snapshot_getter(profile_id)
		if driver is None or driver is not getSynth() or not isinstance(snapshot, dict):
			return None
		if not _requires_full_overlay(config.conf, driver, snapshot):
			return None
		return make_voice_profile_overlay_trigger(profile_id, config.conf, driver, snapshot)
	except Exception:
		return None
