# _speech_core/key_labels.py
"""Runtime support for ClassicSpeech key-label renames and mutes.

This deliberately reuses NVDA's own key-name sources instead of maintaining a
parallel key table. NVDA builds keyboard gesture display names from
``vkCodes.byName`` and ``keyLabels.localizedKeyLabels``. ClassicSpeech applies
user renames/mutes to that localized label table for normal keyboard speech,
but temporarily restores NVDA's original table while input help is speaking so
input help remains a native, predictable island.
"""

import copy
import time

import config
import logHandler

log = logHandler.log


def _ensure_classic_speech_section():
	"""Return the persistent base section, never a transient profile overlay."""
	try:
		baseConf = config.conf.profiles[0]
	except Exception:
		baseConf = config.conf
	if "classicSpeech" not in baseConf:
		baseConf["classicSpeech"] = {}
	conf = baseConf["classicSpeech"]
	if "keyLabelData" not in conf:
		conf["keyLabelData"] = {}
	data = conf["keyLabelData"]
	if "renames" not in data:
		data["renames"] = {}
	if "mutedLabels" not in data:
		data["mutedLabels"] = []
	return conf


def _normalize_key_name(key_name) -> str:
	value = str(key_name or "").strip()
	# Printable uppercase letters are intentionally separate from lowercase letters
	# so NVDA's uppercase pitch behavior can remain meaningful while users can
	# still rename/mute capital key echo independently. Store them under a stable
	# internal canonical name rather than relying on dictionary case sensitivity.
	if len(value) == 1 and value.isalpha() and value.isupper():
		return "upper:" + value.lower()
	if value.startswith("upper:") and len(value) == len("upper:a"):
		letter = value.split(":", 1)[1].lower()
		if len(letter) == 1 and letter.isalpha():
			return "upper:" + letter
	return value.lower()


def _display_label_for_canonical_key(canonical: str, fallback: str = "") -> str:
	canonical = str(canonical or "").strip()
	if canonical.startswith("upper:") and len(canonical) == len("upper:a"):
		letter = canonical.split(":", 1)[1]
		if len(letter) == 1 and letter.isalpha():
			return letter.upper()
	return str(fallback or canonical)


def _get_default_label_table():
	"""Return the unmodified NVDA key-label table when the runtime has it."""
	try:
		if _runtime._originalLabels is not None:
			return _runtime._originalLabels
	except Exception:
		pass
	try:
		from keyLabels import localizedKeyLabels
		return localizedKeyLabels
	except Exception:
		return {}




# Static printable entries that NVDA generates dynamically from keyboard
# gestures instead of listing in vkCodes.byName/keyLabels.py. These are a
# conservative US-layout baseline for v30; a future keyboard-handler layer can
# derive this from the active Windows keyboard layout.
_GENERATED_DIGIT_KEY_LABELS = [(str(number), str(number)) for number in range(0, 10)]
_GENERATED_UPPER_LETTER_KEY_LABELS = [("upper:" + chr(code), chr(code).upper()) for code in range(ord("a"), ord("z") + 1)]
_GENERATED_LOWER_LETTER_KEY_LABELS = [(chr(code), chr(code)) for code in range(ord("a"), ord("z") + 1)]
_GENERATED_LETTER_KEY_LABELS = _GENERATED_UPPER_LETTER_KEY_LABELS + _GENERATED_LOWER_LETTER_KEY_LABELS
_GENERATED_PUNCTUATION_KEY_LABELS = [
	("`", "grave"),
	("-", "minus"),
	("=", "equals"),
	("[", "left bracket"),
	("]", "right bracket"),
	("\\", "backslash"),
	(";", "semicolon"),
	("'", "apostrophe"),
	(",", "comma"),
	(".", "period"),
	("/", "slash"),
	("plus", "plus"),
]
_GENERATED_PRINTABLE_KEY_LABELS = (
	_GENERATED_DIGIT_KEY_LABELS
	+ _GENERATED_LETTER_KEY_LABELS
	+ _GENERATED_PUNCTUATION_KEY_LABELS
)
_GENERATED_DIGIT_KEYS = {key for key, _label in _GENERATED_DIGIT_KEY_LABELS}
_GENERATED_UPPER_LETTER_KEYS = {key for key, _label in _GENERATED_UPPER_LETTER_KEY_LABELS}
_GENERATED_LOWER_LETTER_KEYS = {key for key, _label in _GENERATED_LOWER_LETTER_KEY_LABELS}
_GENERATED_LETTER_KEYS = _GENERATED_UPPER_LETTER_KEYS | _GENERATED_LOWER_LETTER_KEYS
_GENERATED_PUNCTUATION_KEYS = {key for key, _label in _GENERATED_PUNCTUATION_KEY_LABELS}
_GENERATED_PRINTABLE_KEYS = {key for key, _label in _GENERATED_PRINTABLE_KEY_LABELS}

def get_known_key_labels():
	"""Return rows of (canonicalKeyName, defaultSpokenLabel).

	The canonical key name is lower-case because NVDA's vkCodes.byName is already
	case-insensitive. The default spoken label must come from NVDA's original
	key-label table, not the live patched table. Otherwise a muted key such as
	``f1`` can erase the settings UI row itself and leave only ``, muted``.
	"""
	try:
		import vkCodes
	except Exception:
		log.exception("ClassicSpeech: failed to import NVDA key label tables")
		return []

	label_table = _get_default_label_table()
	row_map = {}

	# NVDA's named keys.
	keys = sorted(set(getattr(vkCodes, "byName", {}).keys()), key=str.lower)
	for key in keys:
		canonical = _normalize_key_name(key)
		if not canonical:
			continue
		default_label = str(label_table.get(canonical, canonical))
		if not default_label.strip():
			default_label = canonical
		row_map[canonical] = default_label

	# Printable keys that NVDA's KeyboardInputGesture.mainKeyName can synthesize
	# directly from vkCode/MapVirtualKeyEx and therefore do not appear in
	# vkCodes.byName. Adding them here lets the existing key-label runtime rename
	# or mute their display names without a keyboard-handler rewrite.
	for key, default_label in _GENERATED_PRINTABLE_KEY_LABELS:
		canonical = _normalize_key_name(key)
		if not canonical or canonical in row_map:
			continue
		configured_default = str(label_table.get(canonical, default_label))
		if not configured_default.strip():
			configured_default = default_label or _display_label_for_canonical_key(canonical, canonical)
		row_map[canonical] = _display_label_for_canonical_key(canonical, configured_default)

	def sort_key(item):
		canonical, label = item
		if canonical in _GENERATED_DIGIT_KEYS:
			return (0, int(canonical), canonical)
		if canonical in _GENERATED_UPPER_LETTER_KEYS:
			return (1, ord(canonical.split(":", 1)[1]), canonical)
		if canonical in _GENERATED_LOWER_LETTER_KEYS:
			return (2, ord(canonical), canonical)
		if canonical in _GENERATED_PUNCTUATION_KEYS:
			return (3, label.lower(), canonical)
		return (4, label.lower(), canonical)

	return sorted(row_map.items(), key=sort_key)


def get_key_label_config():
	conf = _ensure_classic_speech_section()
	data = conf.get("keyLabelData", {})
	try:
		renames = dict(data.get("renames", {}))
	except Exception:
		renames = {}
	try:
		muted = list(data.get("mutedLabels", []))
	except Exception:
		muted = []
	return {
		"renames": {
			_normalize_key_name(key): str(value)
			for key, value in renames.items()
			if _normalize_key_name(key) and str(value).strip()
		},
		"mutedLabels": sorted({_normalize_key_name(key) for key in muted if _normalize_key_name(key)}),
	}


def save_key_label_config(config_data: dict):
	conf = _ensure_classic_speech_section()
	data = conf["keyLabelData"]
	renames = dict((config_data or {}).get("renames", {}))
	muted = list((config_data or {}).get("mutedLabels", []))
	data["renames"] = {
		_normalize_key_name(key): str(value).strip()
		for key, value in renames.items()
		if _normalize_key_name(key) and str(value).strip()
	}
	data["mutedLabels"] = sorted({_normalize_key_name(key) for key in muted if _normalize_key_name(key)})


_LAST_PHYSICAL_PRINTABLE_KEY = {"key": "", "expires": 0.0}
_KEY_ECHO_WINDOW_SECONDS = 0.75


def _remember_physical_printable_key(canonical: str):
	canonical = _normalize_key_name(canonical)
	if canonical in _GENERATED_PRINTABLE_KEYS or canonical == "space" or canonical.startswith("upper:"):
		_LAST_PHYSICAL_PRINTABLE_KEY["key"] = canonical
		_LAST_PHYSICAL_PRINTABLE_KEY["expires"] = time.time() + _KEY_ECHO_WINDOW_SECONDS
	else:
		_LAST_PHYSICAL_PRINTABLE_KEY["key"] = ""
		_LAST_PHYSICAL_PRINTABLE_KEY["expires"] = 0.0


def _consume_matching_physical_key(canonical: str) -> bool:
	canonical = _normalize_key_name(canonical)
	now = time.time()
	if now > float(_LAST_PHYSICAL_PRINTABLE_KEY.get("expires", 0.0) or 0.0):
		_LAST_PHYSICAL_PRINTABLE_KEY["key"] = ""
		_LAST_PHYSICAL_PRINTABLE_KEY["expires"] = 0.0
		return False
	expected = _LAST_PHYSICAL_PRINTABLE_KEY.get("key", "")
	if expected != canonical:
		# Caps Lock and some layout paths can report the physical letter without
		# Shift while the resulting typed echo is uppercase. In that case, consume
		# the matching letter key but still apply the uppercase entry's settings.
		if canonical.startswith("upper:"):
			letter = canonical.split(":", 1)[1]
			if expected != letter:
				return False
		else:
			return False
	_LAST_PHYSICAL_PRINTABLE_KEY["key"] = ""
	_LAST_PHYSICAL_PRINTABLE_KEY["expires"] = 0.0
	return True


def _canonicalize_gesture_key_name(gesture) -> str:
	# Prefer NVDA's KeyboardInputGesture.mainKeyName when available because it
	# already accounts for printable keys better than parsing str(gesture). Use the
	# gesture text as an additional hint for Shift+letter so uppercase typed echo
	# can be configured separately from lowercase echo.
	try:
		gesture_text = str(gesture or "")
	except Exception:
		gesture_text = ""
	shifted = "+shift+" in ("+" + gesture_text.lower().replace(":", "+")) or gesture_text.lower().endswith(":shift")

	for attr in ("mainKeyName", "normalizedMainKeyName"):
		try:
			value = getattr(gesture, attr)
			if callable(value):
				value = value()
		except Exception:
			value = ""
		text = str(value or "").strip()
		if len(text) == 1 and text.isalpha() and shifted:
			return "upper:" + text.lower()
		canonical = _canonicalize_typed_echo_text(text)
		if canonical:
			return canonical
	try:
		text = gesture_text
		if ":" in text:
			text = text.rsplit(":", 1)[-1]
		parts = [part for part in text.split("+") if part]
		main = parts[-1] if parts else text
		if len(main) == 1 and main.isalpha() and any(part.lower() == "shift" for part in parts):
			return "upper:" + main.lower()
		return _canonicalize_typed_echo_text(main)
	except Exception:
		return ""



class KeyLabelRuntime:
	"""Applies ClassicSpeech key label overrides to NVDA's localized key table."""

	def __init__(self):
		self._installed = False
		self._originalLabels = None
		self._inputHelpOriginal = None
		self._executeGestureOriginal = None

	def install(self):
		try:
			from keyLabels import localizedKeyLabels
		except Exception:
			log.exception("ClassicSpeech: failed to install key-label runtime")
			return
		if self._originalLabels is None:
			self._originalLabels = copy.deepcopy(localizedKeyLabels)
		self._installed = True
		self.apply_from_config()
		self._install_input_help_bypass()
		self._install_key_echo_tracker()

	def terminate(self):
		self._restore_key_echo_tracker()
		self._restore_input_help_bypass()
		if not self._installed or self._originalLabels is None:
			return
		try:
			from keyLabels import localizedKeyLabels
			localizedKeyLabels.clear()
			localizedKeyLabels.update(copy.deepcopy(self._originalLabels))
		except Exception:
			log.exception("ClassicSpeech: failed to restore NVDA key labels")
		finally:
			self._installed = False


	def _restore_original_labels_temporarily(self):
		if self._originalLabels is None:
			return
		try:
			from keyLabels import localizedKeyLabels
			localizedKeyLabels.clear()
			localizedKeyLabels.update(copy.deepcopy(self._originalLabels))
		except Exception:
			log.debug("ClassicSpeech: failed to temporarily restore key labels", exc_info=True)

	def _install_input_help_bypass(self):
		"""Keep NVDA input help completely native.

		Key-label renames/mutes are useful for normal keyboard speech, but input
		help is a diagnostic/exploration mode. Restoring the original table around
		NVDA's input-help handler prevents renamed/muted labels from changing what
		input help reports.
		"""
		try:
			import inputCore
			manager = inputCore.manager
			if getattr(manager, "_classicSpeechKeyLabelInputHelpBypassInstalled", False):
				return
			original = manager._handleInputHelp
			runtime = self

			def wrapped_handle_input_help(*args, **kwargs):
				runtime._restore_original_labels_temporarily()
				try:
					return original(*args, **kwargs)
				finally:
					try:
						runtime.apply_from_config()
					except Exception:
						log.debug("ClassicSpeech: failed to reapply key labels after input help", exc_info=True)

			manager._classicSpeechKeyLabelInputHelpOriginal = original
			manager._classicSpeechKeyLabelInputHelpBypassInstalled = True
			manager._handleInputHelp = wrapped_handle_input_help
		except Exception:
			log.exception("ClassicSpeech: failed to install input-help key-label bypass")

	def _restore_input_help_bypass(self):
		try:
			import inputCore
			manager = inputCore.manager
			if not getattr(manager, "_classicSpeechKeyLabelInputHelpBypassInstalled", False):
				return
			original = getattr(manager, "_classicSpeechKeyLabelInputHelpOriginal", None)
			if original is not None:
				manager._handleInputHelp = original
			manager._classicSpeechKeyLabelInputHelpOriginal = None
			manager._classicSpeechKeyLabelInputHelpBypassInstalled = False
		except Exception:
			log.debug("ClassicSpeech: failed to restore input-help key-label bypass", exc_info=True)

	def _install_key_echo_tracker(self):
		"""Remember the last physical printable key briefly.

		This lets typed-character echo customization apply only to actual typed
		keypresses. Review/caret/backspace speech can use identical spelling
		sequences, so the speech hook alone is not enough context.
		"""
		try:
			import inputCore
			manager = inputCore.manager
			if getattr(manager, "_classicSpeechKeyEchoTrackerInstalled", False):
				return
			original = manager.executeGesture

			def wrapped_execute_gesture(gesture, *args, **kwargs):
				try:
					canonical = _canonicalize_gesture_key_name(gesture)
					_remember_physical_printable_key(canonical)
				except Exception:
					log.debug("ClassicSpeech: failed to track key echo gesture", exc_info=True)
				return original(gesture, *args, **kwargs)

			manager._classicSpeechKeyEchoTrackerOriginal = original
			manager._classicSpeechKeyEchoTrackerInstalled = True
			manager.executeGesture = wrapped_execute_gesture
		except Exception:
			log.exception("ClassicSpeech: failed to install key echo tracker")

	def _restore_key_echo_tracker(self):
		try:
			import inputCore
			manager = inputCore.manager
			if not getattr(manager, "_classicSpeechKeyEchoTrackerInstalled", False):
				return
			original = getattr(manager, "_classicSpeechKeyEchoTrackerOriginal", None)
			if original is not None:
				manager.executeGesture = original
			manager._classicSpeechKeyEchoTrackerOriginal = None
			manager._classicSpeechKeyEchoTrackerInstalled = False
		except Exception:
			log.debug("ClassicSpeech: failed to restore key echo tracker", exc_info=True)

	def apply_from_config(self):
		self.apply_config(get_key_label_config())

	def apply_config(self, config_data: dict):
		if self._originalLabels is None:
			try:
				from keyLabels import localizedKeyLabels
			except Exception:
				return
			self._originalLabels = copy.deepcopy(localizedKeyLabels)

		try:
			from keyLabels import localizedKeyLabels
			localizedKeyLabels.clear()
			localizedKeyLabels.update(copy.deepcopy(self._originalLabels))

			renames = dict((config_data or {}).get("renames", {}))
			muted = set((config_data or {}).get("mutedLabels", []))

			for key in muted:
				canonical = _normalize_key_name(key)
				if canonical:
					localizedKeyLabels[canonical] = ""

			for key, label in renames.items():
				canonical = _normalize_key_name(key)
				value = str(label).strip()
				if canonical and value and canonical not in muted:
					localizedKeyLabels[canonical] = value
		except Exception:
			log.exception("ClassicSpeech: failed to apply key labels")


_runtime = KeyLabelRuntime()


def install_key_label_runtime():
	_runtime.install()
	return _runtime


def get_key_label_runtime():
	"""Return the shared runtime without enabling its ClassicSpeech changes."""
	return _runtime


def apply_key_labels_live(config_data=None):
	_runtime.apply_config(config_data if config_data is not None else get_key_label_config())

# Canonicalization for typed-character echo. NVDA often sends printable
# keyboard echo as spelling sequences rather than through localizedKeyLabels.
# Keep this deliberately narrow for v30a: one key-name string per utterance.
_TYPED_ECHO_SPOKEN_ALIASES = {
	"space": "space",
	"dot": ".",
	"period": ".",
	"full stop": ".",
	"tick": "'",
	"apostrophe": "'",
	"quote": "'",
	"comma": ",",
	"slash": "/",
	"backslash": "\\",
	"semicolon": ";",
	"colon": ":",
	"minus": "-",
	"dash": "-",
	"hyphen": "-",
	"equals": "=",
	"equal": "=",
	"left bracket": "[",
	"right bracket": "]",
	"grave": "`",
	"backquote": "`",
}


def _canonicalize_typed_echo_text(text: str) -> str:
	value = str(text or "").strip()
	if not value:
		return ""
	if len(value) == 1:
		if value.isalpha() and value.isupper():
			return "upper:" + value.lower()
		return value.lower()
	return _TYPED_ECHO_SPOKEN_ALIASES.get(" ".join(value.lower().split()), value.lower())


def apply_key_label_to_spelling_sequence(tokens):
	"""Apply key-label rename/mute settings to NVDA typed-character echo.

	NVDA speaks typed characters as spelling sequences such as::

		[SuppressUnicodeNormalizationCommand(True), CharacterModeCommand(True),
		 'a', EndUtteranceCommand(), SuppressUnicodeNormalizationCommand(False)]

	ClassicSpeech normally bypasses these sequences so literal text stays native.
	For key-label customization, only touch the single spoken key string and leave
	all other spelling/literal review speech alone.

	Return ``None`` when no change is needed, a replacement sequence when a rename
	applies, or an empty list when the key is muted.
	"""
	try:
		texts = [item for item in tokens if isinstance(item, str) and item.strip()]
		if len(texts) != 1:
			return None
		original_text = texts[0]
		canonical = _canonicalize_typed_echo_text(original_text)
		if not canonical:
			return None
		# Only alter key echo that follows the matching physical printable key.
		# Caret review, backspace deletion echo, and speakSpelling can produce the
		# same speech commands but must remain native.
		if not _consume_matching_physical_key(canonical):
			return None

		config_data = get_key_label_config()
		muted = set(config_data.get("mutedLabels", []))
		renames = dict(config_data.get("renames", {}))

		if canonical in muted:
			return []

		replacement = str(renames.get(canonical, "")).strip()
		if not replacement:
			return None

		# Multi-character replacements should be spoken as a normal word/phrase, not
		# character-by-character. Preserve utterance/normalization commands and
		# uppercase pitch hints so renamed uppercase letters retain NVDA's capital
		# indication. Only drop character mode for multi-character replacements.
		try:
			from speech.commands import CharacterModeCommand
		except Exception:
			CharacterModeCommand = ()
		multi = len(replacement) != 1
		out = []
		replaced = False
		for item in tokens:
			if isinstance(item, str) and item == original_text and not replaced:
				out.append(replacement)
				replaced = True
				continue
			if multi and CharacterModeCommand and isinstance(item, CharacterModeCommand):
				continue
			out.append(item)
		return out
	except Exception:
		log.debug("ClassicSpeech: failed to apply key label to spelling sequence", exc_info=True)
		return None
