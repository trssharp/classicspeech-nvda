import logHandler

from .debug import should_debug_log

from speech.commands import (
	CharacterModeCommand,
	EndUtteranceCommand,
	PitchCommand,
	SuppressUnicodeNormalizationCommand,
)

from ..cancelable import unwrap_cancelable
from ..maps import ALL_SPOKEN_ROLES_LOWER

log = logHandler.log


class LiteralReviewBypass:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _count_instances(self, tokens, cls):
		return sum(1 for t in tokens if isinstance(t, cls))

	def _string_tokens(self, tokens):
		return [t for t in tokens if isinstance(t, str)]

	def _meaningful_string_tokens(self, tokens):
		return [s.strip() for s in self._string_tokens(tokens) if s and s.strip()]

	def _looks_like_single_key(self, token):
		if not isinstance(token, str):
			return False
		s = token.strip()
		if not s:
			return False
		if len(s) == 1:
			return True
		return s.lower() in {
			"space",
			"tab",
			"enter",
			"escape",
			"esc",
			"delete",
			"del",
			"insert",
			"ins",
			"home",
			"end",
			"pageup",
			"pagedown",
			"left",
			"right",
			"up",
			"down",
			"f1",
			"f2",
			"f3",
			"f4",
			"f5",
			"f6",
			"f7",
			"f8",
			"f9",
			"f10",
			"f11",
			"f12",
		}

	def _looks_like_modifier_prefix(self, token):
		if not isinstance(token, str):
			return False
		lower = token.strip().lower()
		return "+" in lower and any(
			mod in lower for mod in ("alt+", "ctrl+", "shift+", "win+", "nvda+")
		)

	def _looks_like_menuish_marker(self, token):
		if not isinstance(token, str):
			return False
		return token.strip().lower() in {
			"submenu",
			"sub menu",
			"menu",
			"menu item",
			"menuitem",
		}

	def _is_compact_ui_accelerator_sequence(self, tokens, context):
		"""
		Narrow bypass for menu/dialog accelerator cases.
		Do not allow long spelling/review sequences through.
		"""
		char_mode_count = self._count_instances(tokens, CharacterModeCommand)
		end_utt_count = self._count_instances(tokens, EndUtteranceCommand)
		pitch_count = self._count_instances(tokens, PitchCommand)
		suppress_count = self._count_instances(tokens, SuppressUnicodeNormalizationCommand)

		if end_utt_count > 0:
			return False
		if pitch_count > 0:
			return False
		if suppress_count > 0:
			return False

		if char_mode_count not in (1, 2):
			return False

		meaningful = self._meaningful_string_tokens(tokens)
		if not meaningful:
			return False

		label_tokens = [s for s in meaningful if len(s) > 1]
		if not label_tokens:
			return False

		last_meaningful = meaningful[-1]
		if self._looks_like_single_key(last_meaningful):
			if context == "menu":
				return True
			return len(meaningful) <= 2

		for i, tok in enumerate(tokens):
			if not self._looks_like_modifier_prefix(tok):
				continue
			if i + 1 < len(tokens) and isinstance(tokens[i + 1], CharacterModeCommand):
				if i + 2 < len(tokens) and self._looks_like_single_key(tokens[i + 2]):
					return True
			elif i + 1 < len(tokens) and self._looks_like_single_key(tokens[i + 1]):
				return True

		if context == "menu" and any(self._looks_like_menuish_marker(t) for t in tokens):
			return True

		return False

	def _is_spelling_sequence(self, tokens, context):
		hasSuppress = any(
			isinstance(t, SuppressUnicodeNormalizationCommand) for t in tokens
		)
		hasCharMode = any(isinstance(t, CharacterModeCommand) for t in tokens)
		hasPitch = any(isinstance(t, PitchCommand) for t in tokens)
		hasEndUtterance = any(isinstance(t, EndUtteranceCommand) for t in tokens)

		strings = self._string_tokens(tokens)
		short_strings = [s for s in strings if len(s.strip()) <= 3]

		if self._is_compact_ui_accelerator_sequence(tokens, context):
			if should_debug_log():
				log.debug(
					"Compact UI accelerator sequence detected; allowing ClassicSpeech processing"
				)
			return False

		if hasSuppress and (hasCharMode or hasPitch or hasEndUtterance):
			return True

		if hasCharMode and hasEndUtterance:
			return True

		if hasCharMode and strings and len(short_strings) >= max(1, len(strings) - 1):
			return True

		return False

	def _sequence_has_edit_document_object_marker(self, meaningful):
		"""Return True when a focused edit/document sequence looks like object speech.

		Caret/review/say-all text inside editable surfaces must bypass semantic
		classification, even when the text contains words that are also role
		labels such as ``region``.  Object focus speech, however, usually carries
		the real focused role (``edit``, ``editable text``, ``document``) or a
		compatible container marker for combo-edit fields.
		"""
		focus_role_key = self._get_focus_role_key()
		if focus_role_key not in {"editabletext", "document", "terminal"}:
			return False

		compatible_object_roles = {focus_role_key}
		if focus_role_key == "editabletext":
			compatible_object_roles.update({"editcombo", "combobox", "window"})
		elif focus_role_key == "document":
			compatible_object_roles.update({"window"})
		elif focus_role_key == "terminal":
			compatible_object_roles.update({"window"})

		for text in meaningful or []:
			role_key = self._normalize_role_key(text)
			if role_key in compatible_object_roles:
				return True
			if self._roles_compatible(role_key, focus_role_key):
				return True
		return False

	def _has_say_all_or_review_callback(self, tokens):
		for tok in tokens or []:
			if isinstance(tok, str):
				continue
			name = tok.__class__.__name__.lower()
			if "callback" in name or "line" in str(tok).lower():
				return True
		return False

	def _is_likely_literal_text_review(self, tokens, context):
		"""
		Avoid semantic classification for literal caret/review text.

		The important hard case is edit/document say-all text.  NVDA can send a
		wrapped line as multiple string fragments plus callbacks; any word in that
		text may accidentally match a spoken role label (for example ``region``).
		When focus is an edit/document surface, treat text as literal unless the
		sequence clearly contains the focused object's own role marker.
		"""
		if context == "menu":
			return False

		string_tokens = self._string_tokens(tokens)
		meaningful = [s.strip() for s in string_tokens if s and s.strip()]
		if not meaningful:
			return False

		if any(isinstance(t, CharacterModeCommand) for t in tokens):
			return False
		if any(isinstance(t, PitchCommand) for t in tokens):
			return False
		if any(isinstance(t, EndUtteranceCommand) for t in tokens):
			return False
		if any(isinstance(t, SuppressUnicodeNormalizationCommand) for t in tokens):
			return False

		focus_role_key = self._get_focus_role_key()
		if focus_role_key in {"editabletext", "document", "terminal"}:
			joined_text = " ".join(meaningful).strip()
			if joined_text.startswith("*"):
				return False
			if self._sequence_has_edit_document_object_marker(meaningful):
				return False
			# Strong bouncer: literal edit/document text can be one fragment, many
			# fragments, or say-all callback chunks.  Bypass all of it unchanged.
			return True

		# Outside text controls, keep the old narrow guard: only bypass a single
		# literal fragment if it exactly matches a spoken role label.  This fixes
		# object review in dialogs without disabling normal focus speech.
		if len(meaningful) != 1:
			return False

		text = meaningful[0]
		if len(text) > 64:
			return False

		normalized = text.lower().strip().rstrip(".:")
		return normalized in ALL_SPOKEN_ROLES_LOWER


	def should_bypass_literal_review(self, speechSequence):
		"""Return True when NVDA is speaking literal caret/review text.

		Review text must be passed through completely unchanged. This check is
		intentionally exposed so the outer speech hook can run it before menu
		hints or structural menu suppression have a chance to touch the sequence.
		"""
		try:
			tokens = list(unwrap_cancelable(speechSequence))
		except Exception:
			return False
		if not tokens:
			return False
		try:
			context = self._get_focus_context()
		except Exception:
			context = "dialog"
		return self._is_likely_literal_text_review(tokens, context)

	# -------------------------
	# Menu navigation markers
	# -------------------------
