"""Speech-manager trigger adapter for a temporary ClassicSpeech Voice Profile overlay."""
from __future__ import annotations


def _do_not_save_settings(*args, **kwargs):
	return None


def settings_gui_open():
	"""True while the NVDA menu or a settings dialog is open.

	NVDA doesn't switch configuration profiles then, so that settings changed in
	a dialog are saved in the profile the user was using. ClassicSpeech's voice
	overlays follow the same rule: the settings dialogs of NVDA and ClassicSpeech
	mark themselves with ``shouldSuspendConfigProfileTriggers``.
	Use this same uncached predicate at automatic voice generation and queued
	trigger entry. A shown marked window suspends routing even after Alt+Tab;
	no foreground-window policy or native configuration-profile reset is needed.
	"""
	try:
		import gui

		check = getattr(gui, "shouldConfigProfileTriggersBeSuspended", None)
		return bool(check()) if callable(check) else False
	except Exception:
		return False


def keep_settings_out_of_nvda_config(driver):
	"""Stop a synthesizer instance from saving its settings as the user's NVDA voice settings.

	NVDA saves a synthesizer's current settings to its configuration whenever
	it saves the configuration, and when it unloads the synthesizer. A
	synthesizer ClassicSpeech loads only to speak or edit a scheme voice holds
	that voice's settings, which must never become the user's settings.
	Use it only on such a synthesizer, never on the one NVDA speaks with.
	"""
	if driver is None:
		return
	try:
		driver._unregisterConfigSaveAction()
	except Exception:
		pass
	try:
		driver.saveSettings = _do_not_save_settings
	except Exception:
		pass


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


class CrossSynthProfileTrigger:
	"""Speak one scheme item with a different synthesizer.

	``enter`` pushes an in-memory configuration profile naming the other
	synthesizer and its settings. NVDA's speech manager then calls
	``synthDriverHandler.handlePostConfigProfileSwitch``, which loads that
	synthesizer exactly as NVDA's own configuration-profile triggers do, and
	loads the user's synthesizer again after ``exit``. Loading a synthesizer
	takes time, so each switch adds a delay; the Voice editor says so.

	NVDA saves a synthesizer's settings when it unloads it. Before ``exit``
	lets NVDA unload the other synthesizer, it stops that synthesizer from
	saving, so the item's voice never replaces the user's own settings for it.

	While a settings dialog or the NVDA menu is open, the item speaks with the
	active synthesizer instead (``settings_gui_open``). Settings NVDA stores
	while the other synthesizer speaks are kept when it exits, apart from speech
	settings, which belong to the synthesizers being switched.
	"""

	_shouldNotifyProfileSwitch = False
	hasProfile = True

	def __init__(
		self,
		item_id: str,
		synth_name: str,
		settings: dict,
		config_manager=None,
		profile_factory=None,
		active_synth_getter=None,
	):
		self._item_id = str(item_id)
		self._synth_name = str(synth_name)
		self._settings = dict(settings or {})
		self._config = config_manager
		self._profile_factory = profile_factory
		self._active_synth_getter = active_synth_getter
		self._profile = None
		self._switched = False
		self._paused = False

	@property
	def spec(self):
		return f"classicSpeech:scheme:{self._item_id}:{self._synth_name}"

	def _config_manager(self):
		if self._config is not None:
			return self._config
		import config
		return config.conf

	def _new_profile(self):
		if self._profile_factory is not None:
			profile = self._profile_factory()
		else:
			from configobj import ConfigObj
			profile = ConfigObj(indent_type="\t", encoding="UTF-8")
		profile["speech"] = {"synth": self._synth_name, self._synth_name: dict(self._settings)}
		try:
			profile.filename = None
		except Exception:
			pass
		return profile

	def _active_synth(self):
		try:
			if self._active_synth_getter is not None:
				return self._active_synth_getter()
			from synthDriverHandler import getSynth

			return getSynth()
		except Exception:
			return None

	def _active_synth_name(self):
		return str(getattr(self._active_synth(), "name", "") or "")

	def _belongs_to_overlay(self, path, key, value):
		"""Speech settings belong to the synthesizer switch, except a synthesizer the user chose."""
		if path[:1] != ("speech",):
			return False
		return not (path == ("speech",) and key == "synth" and str(value) != self._synth_name)

	def enter(self):
		if self._profile is not None or self._paused:
			return
		if settings_gui_open():
			self._paused = True
			return
		manager = self._config_manager()
		profile = self._new_profile()
		# Only a synthesizer this trigger makes NVDA load may be kept from saving.
		self._switched = self._active_synth_name() != self._synth_name
		manager.profiles.append(profile)
		try:
			manager._handleProfileSwitch(shouldNotify=False)
		except Exception:
			manager.profiles.remove(profile)
			raise
		self._profile = profile

	def exit(self):
		self._paused = False
		profile = self._profile
		if profile is None:
			return
		manager = self._config_manager()
		self._profile = None
		if self._switched:
			driver = self._active_synth()
			if str(getattr(driver, "name", "") or "") == self._synth_name:
				keep_settings_out_of_nvda_config(driver)
		from .voice_profile_overlay import carry_writes, writes_to_carry

		writes = writes_to_carry(profile, self._belongs_to_overlay)
		try:
			if manager.profiles and manager.profiles[-1] is profile:
				manager.profiles.pop()
			else:
				manager.profiles.remove(profile)
		except ValueError:
			return
		manager._handleProfileSwitch(shouldNotify=False)
		carry_writes(manager, writes)


class VoiceProfileOverlayTrigger:
	"""Minimal private-NVDA trigger contract used by ConfigProfileTriggerCommand.

	SpeechManager only needs ``hasProfile``, ``enter``, ``exit``, and a stable
	``spec`` here. ``_shouldNotifyProfileSwitch=False`` prevents unrelated NVDA
	profile consumers (such as braille) from being notified for speech-only scope.

	While a settings dialog or the NVDA menu is open, the trigger does nothing,
	so NVDA speaks with the user's own voice settings and changes to them are
	kept (``settings_gui_open``). A preview the user asked for still applies.
	"""

	_shouldNotifyProfileSwitch = False
	hasProfile = True

	def __init__(self, profile_id: str, overlay, direct_transaction=None, preview=False):
		self._profile_id = str(profile_id)
		self._overlay = overlay
		self._direct_transaction = direct_transaction
		self._preview = bool(preview)
		self._paused = False

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
		if not self._preview and settings_gui_open():
			_trace(f"trigger paused while settings are open profile={self._profile_id}")
			self._paused = True
			return
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
		# After a paused enter, nothing is active and both exits do nothing.
		self._paused = False
		if self._direct_transaction is not None:
			self._direct_transaction.exit()
		if self._overlay is not None:
			self._overlay.exit()
