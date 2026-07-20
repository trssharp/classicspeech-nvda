"""Speech-manager trigger adapter for a temporary ClassicSpeech Voice Profile overlay."""
from __future__ import annotations


class VoiceProfileDirectSettingsTransaction:
	"""A Preview-style full setting transaction executed only at a speech queue boundary."""

	def __init__(self, driver, snapshot):
		self._driver = driver
		self._snapshot = dict(snapshot or {})
		self._original = {}
		self.active = False

	@property
	def driver(self):
		return self._driver

	def _setting_ids(self):
		ids = [
			getattr(setting, "id", "")
			for setting in getattr(self._driver, "supportedSettings", ())
		]
		ids = [setting_id for setting_id in ids if setting_id and setting_id in self._snapshot]
		ids = [
			setting_id for setting_id in ids
			if setting_id not in {"rate", "pitch", "volume"}
			or (
				not isinstance(self._snapshot[setting_id], bool)
				and isinstance(self._snapshot[setting_id], (int, float))
			)
		]
		selector_ids = [setting_id for setting_id in ("voice", "variant") if setting_id in ids]
		return selector_ids + [setting_id for setting_id in ids if setting_id not in {"voice", "variant"}]

	def enter(self):
		if self.active:
			return
		setting_ids = self._setting_ids()
		self._original = {setting_id: getattr(self._driver, setting_id) for setting_id in setting_ids}
		try:
			for setting_id in setting_ids:
				setattr(self._driver, setting_id, self._snapshot[setting_id])
		except Exception:
			self._restore()
			raise
		self.active = True

	def _restore(self):
		for setting_id in (["voice"] if "voice" in self._original else []) + [
			setting_id for setting_id in self._original if setting_id != "voice"
		]:
			try:
				setattr(self._driver, setting_id, self._original[setting_id])
			except Exception:
				pass

	def exit(self):
		if not self.active:
			return
		self._restore()
		self._original = {}
		self.active = False


class VoiceProfileOverlayTrigger:
	"""Minimal private-NVDA trigger contract used by ConfigProfileTriggerCommand.

	SpeechManager only needs ``hasProfile``, ``enter``, ``exit``, and a stable
	``spec`` here. ``_shouldNotifyProfileSwitch=False`` prevents unrelated NVDA
	profile consumers (such as braille) from being notified for speech-only scope.
	"""

	_shouldNotifyProfileSwitch = False
	hasProfile = True

	def __init__(self, profile_id: str, overlay, direct_transaction=None):
		self._profile_id = str(profile_id)
		self._overlay = overlay
		self._direct_transaction = direct_transaction

	@property
	def spec(self):
		return f"classicSpeech:voiceProfile:{self._profile_id}"

	def _trace_live_variant_after_reload(self):
		from .voice_profile_overlay import _trace
		try:
			from synthDriverHandler import getSynth
			driver = getSynth()
			_trace(f"post-reload profile={self._profile_id} liveVariant={getattr(driver, 'variant', None)!r}")
		except Exception:
			_trace(f"post-reload profile={self._profile_id} liveVariant=<unavailable>")

	def enter(self):
		from .voice_profile_overlay import _trace
		_trace(f"trigger enter profile={self._profile_id}")
		if self._overlay is not None:
			self._overlay.enter()
		try:
			if self._direct_transaction is not None:
				self._direct_transaction.enter()
			if self._overlay is not None and self._direct_transaction is not None:
				self._overlay.synchronize_from_driver(self._direct_transaction.driver)
		except Exception:
			if self._overlay is not None:
				self._overlay.exit()
			raise
		try:
			import wx
			wx.CallAfter(self._trace_live_variant_after_reload)
		except Exception:
			pass

	def exit(self):
		from .voice_profile_overlay import _trace
		_trace(f"trigger exit profile={self._profile_id}")
		if self._direct_transaction is not None:
			self._direct_transaction.exit()
		if self._overlay is not None:
			self._overlay.exit()
