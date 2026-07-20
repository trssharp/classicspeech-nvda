"""Synthesizer-specific Voice Profile baselines and explicit overrides.

Editable profiles are stored as ``baseline`` (the selected voice's native
settings captured after voice selection) plus ``overrides`` (only values the
user explicitly changed). Legacy flat snapshots remain valid full explicit
overrides for non-voice edits. An explicit Voice edit is a deliberate migration:
the flat record is replaced with the selected voice's native baseline and empty
overrides, so stale dependent legacy values cannot override the new voice.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

import logHandler

from .config_core import _ensure_classic_speech_section, _replace_section_contents, _to_plain_data

log = logHandler.log


def _debug(message: str) -> None:
	"""Emit profile transaction evidence only when ClassicSpeech debug is enabled."""
	try:
		if bool(_ensure_classic_speech_section().get("debugLogging", False)):
			log.info("ClassicSpeech Voice Profiles: %s", message)
	except Exception:
		# Diagnostics must never interfere with settings persistence.
		pass



def _load_registry(value) -> dict:
	"""Decode the schema-approved JSON registry, retaining old in-memory dicts."""
	if isinstance(value, dict):
		return _to_plain_data(value)
	if isinstance(value, str):
		try:
			decoded = json.loads(value)
			if isinstance(decoded, dict):
				return decoded
		except (TypeError, ValueError):
			pass
	return {}


def _dump_registry(registry: dict) -> str:
	return json.dumps(registry, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class VoiceProfileRow:
	profile_id: str
	label: str
	editable: bool


PROFILE_ROWS = (
	VoiceProfileRow("focusNavigation", "Focus and navigation", True),
	VoiceProfileRow("reviewObjectNavigation", "Review and object navigation", True),
	VoiceProfileRow("keyboardEntry", "Keyboard entry", True),
	VoiceProfileRow("systemNotifications", "System and notifications", True),
)
_PROFILE_BY_ID = {row.profile_id: row for row in PROFILE_ROWS}
_VOICE_SETTING_ID = "voice"
_VARIANT_SETTING_ID = "variant"


def _supported_snapshot(driver) -> dict:
	"""Capture the currently exposed driver values without changing the driver."""
	snapshot = {}
	for setting in getattr(driver, "supportedSettings", ()):
		setting_id = getattr(setting, "id", "")
		if not setting_id or setting_id.startswith("_"):
			continue
		try:
			snapshot[setting_id] = _to_plain_data(getattr(driver, setting_id))
		except Exception:
			continue
	return snapshot


def _restore_snapshot(driver, snapshot: dict) -> None:
	"""Restore a capture after a temporary voice probe, even after one error."""
	# Voice first lets dependent values be restored after its native reset.
	setting_ids = ([ _VOICE_SETTING_ID ] if _VOICE_SETTING_ID in snapshot else [])
	setting_ids.extend(setting_id for setting_id in snapshot if setting_id != _VOICE_SETTING_ID)
	for setting_id in setting_ids:
		try:
			setattr(driver, setting_id, snapshot[setting_id])
		except Exception:
			pass


def get_synth_id(driver) -> str:
	return str(getattr(driver, "name", "unknown") or "unknown")


class VoiceProfileStore:
	"""Transactional editor that never changes live speech except an explicit voice probe."""

	def __init__(self, driver, section=None):
		self.driver = driver
		self.synth_id = get_synth_id(driver)
		self._section = section if section is not None else _ensure_classic_speech_section()
		self._opening_section = _to_plain_data(self._section)
		self._working_registry = _load_registry(self._section.get("voiceProfileData", "{}"))
		if not isinstance(self._working_registry, dict):
			self._working_registry = {}
		# A Voice Profiles transaction always owns the complete editable set.
		# This avoids a category becoming routable only after a control-change
		# event happens to materialize its record.
		for row in self.rows:
			if row.editable:
				self._profile_record(row.profile_id)

	@property
	def rows(self):
		return PROFILE_ROWS

	def _editable_row(self, profile_id: str) -> VoiceProfileRow:
		row = _PROFILE_BY_ID.get(profile_id)
		if row is None:
			raise KeyError(profile_id)
		return row

	def _profile_record(self, profile_id: str) -> dict:
		self._editable_row(profile_id)
		synth_profiles = self._working_registry.setdefault(self.synth_id, {})
		record = synth_profiles.get(profile_id)
		if record is None:
			record = {"baseline": _supported_snapshot(self.driver), "overrides": {}}
			synth_profiles[profile_id] = record
		return record

	def _is_new_record(self, record) -> bool:
		return isinstance(record, dict) and isinstance(record.get("baseline"), dict) and isinstance(record.get("overrides"), dict)

	def reset_all_overrides(self) -> None:
		"""Remove every category override for this synth after explicit UI confirmation."""
		_debug(f"reset all overrides synth={self.synth_id} profiles={sorted(self._working_registry.get(self.synth_id, {}))}")
		self._working_registry.pop(self.synth_id, None)

	def get_snapshot(self, profile_id: str):
		"""Return the editor's resolved, display-only baseline plus overrides."""
		record = self._profile_record(profile_id)
		if not self._is_new_record(record):
			# Migration choice: keep old flat snapshots as full explicit overrides.
			return record
		resolved = dict(record["baseline"])
		resolved.update(record["overrides"])
		return resolved

	def get_preview_snapshot(self, profile_id: str) -> dict:
		"""Return voice first plus only explicit overrides for a safe preview."""
		record = self._profile_record(profile_id)
		if not self._is_new_record(record):
			return dict(record)
		preview = {}
		for selector_id in (_VOICE_SETTING_ID, _VARIANT_SETTING_ID):
			if selector_id in record["baseline"]:
				preview[selector_id] = record["baseline"][selector_id]
		preview.update(record["overrides"])
		return {key: value for key, value in preview.items() if value is not None}

	def _capture_voice_baseline(self, voice_value) -> dict:
		"""Temporarily select a voice, capture its native values, restore live state."""
		original = _supported_snapshot(self.driver)
		try:
			setattr(self.driver, _VOICE_SETTING_ID, voice_value)
			return _supported_snapshot(self.driver)
		finally:
			_restore_snapshot(self.driver, original)

	def _capture_variant_baseline(self, voice_value, variant_value) -> dict:
		"""Probe native Voice then Variant defaults without leaking live settings."""
		original = _supported_snapshot(self.driver)
		try:
			if voice_value is not None:
				setattr(self.driver, _VOICE_SETTING_ID, voice_value)
			setattr(self.driver, _VARIANT_SETTING_ID, variant_value)
			return _supported_snapshot(self.driver)
		finally:
			_restore_snapshot(self.driver, original)

	def set_value(self, profile_id: str, setting_id: str, value) -> None:
		_debug(f"set synth={self.synth_id} profile={profile_id} setting={setting_id} value={value!r}")
		record = self._profile_record(profile_id)
		if not self._is_new_record(record):
			value = _to_plain_data(value)
			if setting_id == _VOICE_SETTING_ID:
				record.clear()
				record.update({"baseline": self._capture_voice_baseline(value), "overrides": {}})
				return
			if setting_id == _VARIANT_SETTING_ID:
				voice_value = record.get(_VOICE_SETTING_ID, getattr(self.driver, _VOICE_SETTING_ID, None))
				record.clear()
				record.update({"baseline": self._capture_variant_baseline(voice_value, value), "overrides": {}})
				return
			# Preserve legacy compatibility for non-selector edits.
			record[setting_id] = _to_plain_data(value)
			return
		value = _to_plain_data(value)
		if setting_id == _VOICE_SETTING_ID:
			old_overrides = dict(record["overrides"])
			old_overrides.pop(_VOICE_SETTING_ID, None)
			record["baseline"] = self._capture_voice_baseline(value)
			record["overrides"] = old_overrides
			return
		if setting_id == _VARIANT_SETTING_ID:
			old_overrides = dict(record["overrides"])
			voice_value = record["baseline"].get(_VOICE_SETTING_ID)
			record["baseline"] = self._capture_variant_baseline(voice_value, value)
			old_overrides[_VARIANT_SETTING_ID] = value
			record["overrides"] = old_overrides
			return
		baseline_value = record["baseline"].get(setting_id)
		if value == baseline_value:
			record["overrides"].pop(setting_id, None)
		else:
			record["overrides"][setting_id] = value

	def apply(self) -> None:
		"""Commit every working profile and persist it through NVDA's config manager."""
		payload = _dump_registry(self._working_registry)
		_debug(f"apply synth={self.synth_id} registry={payload}")
		self._section["voiceProfileData"] = payload
		try:
			import config
			save = getattr(config.conf, "save", None)
			if callable(save):
				save()
		except Exception:
			# Do not hide an in-memory commit because a disk write failed; the dialog
			# reports the failure and leaves its Apply button available for retry.
			raise

	def mark_applied(self) -> None:
		self._opening_section = _to_plain_data(self._section)

	def cancel(self) -> None:
		_replace_section_contents(self._section, self._opening_section)
		self._working_registry = _load_registry(self._opening_section.get("voiceProfileData", "{}"))
		if not isinstance(self._working_registry, dict):
			self._working_registry = {}
