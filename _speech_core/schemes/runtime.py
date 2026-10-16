"""Turn Speech and Sound Scheme markers into sounds and voice changes.

``apply_schemes`` runs at the end of ClassicSpeech's speech filter on the final
sequence. It always removes markers. When schemes are enabled it also:

* plays an item's WAV file where its announcement or object starts, optionally
  instead of speaking the announcement;
* plays that WAV file again where a run of formatting or an element begins in
  document text, so the change is heard even when NVDA announces nothing;
* speaks announcements and formatted/element text in the item's voice.

Reading by character, word, line, sentence or paragraph and Say All all arrive
here the same way: the tagging wrappers give every speech sequence the
formatting and elements it starts inside, so an item is heard whichever reading
command produced the text.

Voices that only change rate, pitch or volume use NVDA's inline prosody
commands, so speech keeps flowing. Any other difference (voice, variant,
engine-specific settings or another synthesizer) uses a configuration-profile
trigger, the same queue-safe mechanism as ClassicSpeech Voice Profiles.
"""
from __future__ import annotations

import os
from numbers import Real

import logHandler

from . import store
from ..voice_profile_trigger import settings_gui_open
from .markers import (
	ElementEndMarker,
	ElementStartMarker,
	FormatMarker,
	LabelMarker,
	ObjectMarker,
	SchemeMarker,
	TextStartMarker,
	has_markers,
	strip_markers,
)

log = logHandler.log

_PROSODY_IDS = ("rate", "pitch", "volume")

try:
	from speech.commands import WaveFileCommand as _WaveFileCommand
except Exception:  # Outside NVDA (test harnesses).
	class _WaveFileCommand:
		def __init__(self, fileName):
			self.fileName = fileName


class SchemeSoundCommand(_WaveFileCommand):
	"""A scheme item's sound; distinguishable from NVDA's own wave commands."""

	def __init__(self, fileName, item_id=""):
		super().__init__(fileName)
		self.itemId = item_id

	def __repr__(self):
		return f"SchemeSoundCommand({self.fileName!r}, item={self.itemId!r})"


class _ScanState:
	__slots__ = ("format_items", "elements", "object_items")

	def __init__(self):
		self.format_items = ()
		self.elements = []
		self.object_items = ()

	def copy(self):
		other = _ScanState()
		other.format_items = tuple(self.format_items)
		other.elements = list(self.elements)
		other.object_items = tuple(self.object_items)
		return other

	def range_items(self):
		items = list(self.format_items)
		for _key, element_items in reversed(self.elements):
			items.extend(element_items)
		items.extend(self.object_items)
		return items


#: Formatting and element state carried into the next sequence while say all
#: runs; NVDA's sentence splitting moves the end of a line into the next call.
_carried_state = None
_sound_exists_cache = {}


def reset_carried_state():
	global _carried_state
	_carried_state = None


def _say_all_running() -> bool:
	try:
		from speech.sayAll import SayAllHandler
		return bool(SayAllHandler.isRunning())
	except Exception:
		return False


def _sound_path(path):
	path = str(path or "").strip()
	if not path:
		return ""
	cached = _sound_exists_cache.get(path)
	if cached is None:
		cached = os.path.isfile(path)
		if len(_sound_exists_cache) > 512:
			_sound_exists_cache.clear()
		_sound_exists_cache[path] = cached
	return path if cached else ""


def clear_sound_cache():
	_sound_exists_cache.clear()


def _item_voice(items_cfg, item_id):
	settings = items_cfg.get(item_id)
	if not settings:
		return None
	voice = settings.get("voice")
	if isinstance(voice, dict) and voice.get("enabled"):
		return voice
	return None


def _first_voice_item(items_cfg, candidates):
	for item_id in candidates:
		if _item_voice(items_cfg, item_id):
			return item_id
	return None


def _first_sound_item(items_cfg, candidates, played):
	for item_id in candidates:
		if item_id in played:
			continue
		settings = items_cfg.get(item_id)
		if settings and _sound_path(settings.get("sound")):
			return item_id
	return None


def apply_schemes(sequence, *, allow_prosody=None):
	"""Return ``sequence`` with scheme markers converted; markers never survive."""
	global _carried_state
	items_cfg = store.active_items()
	if not items_cfg:
		reset_carried_state()
		if has_markers(sequence):
			return strip_markers(sequence)
		return sequence
	if not has_markers(sequence) and _carried_state is None:
		# Nothing to do: keep NVDA's own sequence object (native pass-through).
		return sequence

	carrying = _say_all_running()
	state = _carried_state.copy() if (carrying and _carried_state is not None) else _ScanState()
	played = set()
	atoms = []
	pending_label = None
	for entry in sequence:
		if isinstance(entry, SchemeMarker):
			if isinstance(entry, TextStartMarker):
				state = _ScanState()
				state.elements = [(key, tuple(items)) for key, items in entry.elements]
			elif isinstance(entry, ObjectMarker):
				state.object_items = tuple(entry.items)
				sound_item = _first_sound_item(items_cfg, entry.items, played)
				if sound_item:
					played.add(sound_item)
					atoms.append(("sound", sound_item))
			elif isinstance(entry, FormatMarker):
				state.format_items = tuple(entry.items)
				# A restatement repeats formatting the listener already heard
				# start, so only a real change plays the item's sound.
				if not getattr(entry, "restate", False):
					sound_item = _first_sound_item(items_cfg, entry.items, played)
					if sound_item:
						played.add(sound_item)
						atoms.append(("sound", sound_item))
			elif isinstance(entry, ElementStartMarker):
				state.elements.append((entry.key, tuple(entry.items)))
				sound_item = _first_sound_item(items_cfg, entry.items, played)
				if sound_item:
					played.add(sound_item)
					atoms.append(("sound", sound_item))
			elif isinstance(entry, ElementEndMarker):
				for index in range(len(state.elements) - 1, -1, -1):
					if state.elements[index][0] == entry.key:
						del state.elements[index]
						break
			elif isinstance(entry, LabelMarker):
				pending_label = tuple(entry.items)
			continue
		if isinstance(entry, str):
			if pending_label is not None:
				label_items, pending_label = pending_label, None
				sound_item = _first_sound_item(items_cfg, label_items, set())
				if sound_item:
					if sound_item not in played:
						played.add(sound_item)
						atoms.append(("sound", sound_item))
					# "Sound instead of speech" also applies when the sound
					# already played at the start of this object or element.
					if items_cfg[sound_item].get("soundOnly"):
						continue
				voice_item = _first_voice_item(items_cfg, label_items) or _first_voice_item(items_cfg, state.range_items())
			else:
				voice_item = _first_voice_item(items_cfg, state.range_items())
			atoms.append(("text", entry, voice_item))
			continue
		atoms.append(("command", entry))
	_carried_state = state if carrying else None
	if allow_prosody is None:
		allow_prosody = not _contains_profile_commands(sequence)
	return _render(atoms, items_cfg, allow_prosody)


def _contains_profile_commands(sequence) -> bool:
	for entry in sequence:
		name = type(entry).__name__
		if name in ("ConfigProfileTriggerCommand", "RateCommand", "VolumeCommand"):
			return True
	return False


def _render(atoms, items_cfg, allow_prosody):
	"""Group atoms by voice and emit sounds, text and voice commands."""
	segments = []
	current_voice = None
	current = []
	current_has_text = False
	pending = []
	for atom in atoms:
		if atom[0] != "text":
			pending.append(atom)
			continue
		voice = atom[2]
		if current_has_text and voice != current_voice:
			segments.append((current_voice, current))
			current = []
			current_has_text = False
		if not current_has_text:
			current_voice = voice
		current.extend(pending)
		pending = []
		current.append(atom)
		current_has_text = True
	current.extend(pending)
	if current:
		segments.append((current_voice, current))

	plans = {}
	output = []
	for voice_item, segment in segments:
		plan = None
		if voice_item:
			if voice_item not in plans:
				plans[voice_item] = _voice_plan(voice_item, items_cfg, allow_prosody)
			plan = plans[voice_item]
		output.extend(_render_segment(segment, plan, items_cfg))
	return output


def _atom_entries(segment, items_cfg):
	for atom in segment:
		kind = atom[0]
		if kind == "text":
			yield atom[1]
		elif kind == "sound":
			path = _sound_path(items_cfg[atom[1]].get("sound"))
			if path:
				yield SchemeSoundCommand(path, atom[1])
		else:
			yield atom[1]


def _render_segment(segment, plan, items_cfg):
	entries = list(_atom_entries(segment, items_cfg))
	if plan is None:
		return entries
	kind = plan[0]
	if kind == "trigger":
		trigger = plan[1]()
		if trigger is None:
			return entries
		try:
			from speech.commands import ConfigProfileTriggerCommand
		except Exception:
			return entries
		return [ConfigProfileTriggerCommand(trigger, True), *entries, ConfigProfileTriggerCommand(trigger, False)]
	if kind == "prosody":
		return _wrap_prosody(entries, plan[1], plan[2])
	return entries


def _wrap_prosody(entries, begin_factory, reset_factory):
	"""Apply inline prosody around text, restarting it after utterance ends."""
	try:
		from speech.commands import EndUtteranceCommand, PitchCommand
	except Exception:
		EndUtteranceCommand = PitchCommand = None
	begin = begin_factory()
	pitch_offset = 0
	for command in begin:
		if PitchCommand is not None and isinstance(command, PitchCommand):
			pitch_offset = getattr(command, "offset", 0)
	output = []
	active = False
	for entry in entries:
		if EndUtteranceCommand is not None and isinstance(entry, EndUtteranceCommand):
			if active:
				output.extend(reset_factory())
				active = False
			output.append(entry)
			continue
		if PitchCommand is not None and isinstance(entry, PitchCommand) and pitch_offset:
			# NVDA uses pitch commands for capital letters. Keep their relative
			# rise on top of this item's pitch rather than resetting it.
			output.append(PitchCommand(offset=pitch_offset + getattr(entry, "offset", 0)))
			continue
		if isinstance(entry, str) and not active:
			output.extend(begin_factory())
			active = True
		output.append(entry)
	if active:
		output.extend(reset_factory())
	return output


def _numeric(value):
	if isinstance(value, bool) or not isinstance(value, Real):
		return None
	return int(value)


def _prosody_command_types():
	try:
		from speech.commands import PitchCommand, RateCommand, VolumeCommand
	except Exception:
		return {}
	return {"rate": RateCommand, "pitch": PitchCommand, "volume": VolumeCommand}


def _prosody_reaches_synth(driver, setting_ids) -> bool:
	"""True when the synthesizer acts on NVDA's inline commands for these settings.

	A synthesizer lists the commands it understands in ``supportedCommands`` and
	silently ignores every other one. An item whose voice only changes a setting
	the synthesizer ignores would never be heard, so it uses the same
	configuration-profile overlay as a ClassicSpeech Voice Profile instead,
	which sets the values the user chose on the synthesizer itself.
	"""
	types = _prosody_command_types()
	if not types:
		return False
	try:
		supported = set(getattr(driver, "supportedCommands", ()) or ())
	except Exception:
		return False
	if not supported:
		return False
	for setting_id in setting_ids:
		command_type = types.get(setting_id)
		if command_type is None or command_type not in supported:
			return False
	return True


def resolve_voice_snapshot(record):
	"""Voice/Variant selectors plus explicit overrides (same rule as Voice Profiles)."""
	from ..prosody_routing import _resolve_profile_snapshot

	snapshot = _resolve_profile_snapshot(record)
	return dict(snapshot) if isinstance(snapshot, dict) else None


def _voice_plan(item_id, items_cfg, allow_prosody):
	"""Return ``("prosody", begin, reset)``, ``("trigger", factory)`` or ``None``."""
	if settings_gui_open():
		return None
	voice = _item_voice(items_cfg, item_id)
	if voice is None:
		return None
	try:
		import config
		from synthDriverHandler import getSynth
		driver = getSynth()
		active_name = str(getattr(driver, "name", "") or "")
	except Exception:
		return None
	engine = str(voice.get("engine") or "") or active_name
	record = (voice.get("bySynth") or {}).get(engine)
	snapshot = resolve_voice_snapshot(record) if record else None
	if engine != active_name:
		settings = snapshot or {}
		from ..voice_profile_trigger import CrossSynthProfileTrigger
		return ("trigger", lambda: CrossSynthProfileTrigger(item_id, engine, settings))
	if not snapshot:
		return None
	try:
		configured = config.conf["speech"][active_name]
		supported = [getattr(setting, "id", "") for setting in getattr(driver, "supportedSettings", ())]
	except Exception:
		return None
	differences = {}
	for setting_id in supported:
		if not setting_id or setting_id not in snapshot:
			continue
		try:
			current = configured.get(setting_id) if hasattr(configured, "get") else configured[setting_id]
		except Exception:
			current = None
		if current != snapshot[setting_id]:
			differences[setting_id] = snapshot[setting_id]
	if not differences:
		return None
	if allow_prosody and set(differences) <= set(_PROSODY_IDS) and _prosody_reaches_synth(driver, differences):
		offsets = {}
		for setting_id, target in differences.items():
			target_value = _numeric(target)
			base_value = _numeric(configured.get(setting_id) if hasattr(configured, "get") else None)
			# NVDA turns an offset into a multiplier by dividing by the saved
			# setting, so a saved zero has no offset that can express the value
			# the user chose. That item takes the overlay instead.
			if target_value is None or not base_value:
				offsets = None
				break
			offsets[setting_id] = target_value - base_value
		if offsets is not None:
			return ("prosody", lambda: _prosody_commands(offsets, reset=False), lambda: _prosody_commands(offsets, reset=True))
	full_snapshot = dict(snapshot)
	if "rate" not in full_snapshot and "rate" in supported:
		try:
			full_snapshot["rate"] = configured["rate"]
		except Exception:
			pass

	def make_trigger():
		try:
			from ..voice_profile_runtime import make_voice_profile_overlay_trigger
			return make_voice_profile_overlay_trigger(f"scheme:{item_id}", config.conf, driver, full_snapshot)
		except Exception:
			log.debug("ClassicSpeech schemes: voice trigger unavailable for %s", item_id, exc_info=True)
			return None

	return ("trigger", make_trigger)


def _prosody_commands(offsets, reset=False):
	try:
		from speech.commands import PitchCommand, RateCommand, VolumeCommand
	except Exception:
		return []
	types = {"rate": RateCommand, "pitch": PitchCommand, "volume": VolumeCommand}
	commands = []
	for setting_id in _PROSODY_IDS:
		if setting_id not in offsets:
			continue
		command_type = types[setting_id]
		commands.append(command_type() if reset else command_type(offset=offsets[setting_id]))
	return commands


def scheme_sound_only_output(sequence) -> bool:
	"""True when every spoken string was replaced by a scheme sound."""
	has_sound = False
	for entry in sequence:
		if isinstance(entry, str) and entry.strip():
			return False
		if isinstance(entry, SchemeSoundCommand):
			has_sound = True
	return has_sound


# ---------------------------------------------------------------------------
# ClassicSpeech formatter support
# ---------------------------------------------------------------------------

def _state_polarity(token_raw, token_source):
	"""Return ``(state_name, negative)`` for a formatter state token."""
	try:
		import controlTypes
		state = controlTypes.State[str(token_raw).upper()]
	except Exception:
		return str(token_raw or "").upper(), False
	negative_text = ""
	try:
		negative_text = str(state.negativeDisplayString or "").strip().lower()
	except Exception:
		negative_text = ""
	for source in token_source or ():
		if isinstance(source, str) and negative_text and source.strip().lower().rstrip(".:") == negative_text:
			return state.name, True
	return state.name, False


def label_marker_for_token(token):
	"""LabelMarker for a ClassicSpeech role or state token, or ``None``."""
	items_cfg = store.active_items()
	if not items_cfg:
		return None
	kind = getattr(token, "kind", None)
	raw = getattr(token, "raw", None)
	if isinstance(raw, (list, tuple)):
		raw = " ".join(str(part) for part in raw)
	raw = str(raw or "").strip()
	if not raw:
		return None
	items = []
	if kind == "role":
		items.append(f"role.{raw.replace(' ', '').upper()}")
	elif kind == "state":
		state_name, negative = _state_polarity(raw, getattr(token, "source", ()))
		items.append(f"state.{state_name}{'.off' if negative else ''}")
	else:
		return None
	configured = [item_id for item_id in items if item_id in items_cfg]
	return LabelMarker(configured) if configured else None
