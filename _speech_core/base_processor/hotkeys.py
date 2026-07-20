import config
import logHandler

from .debug import should_debug_log

from speech.commands import CharacterModeCommand

from ..settings import (
	HOTKEY_MODE_BOTH,
	HOTKEY_MODE_DIALOGS,
	HOTKEY_MODE_MENUS,
	HOTKEY_MODE_OFF,
	HOTKEY_FORMAT_NATIVE,
	HOTKEY_FORMAT_EXPANDED_NO_PLUS,
	HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
	HOTKEY_TYPES_ACCESS,
	HOTKEY_TYPES_COMMAND,
	HOTKEY_TYPES_BOTH,
)
from ..tokens import TOKEN_HOTKEY

log = logHandler.log


class HotkeyProcessor:
	def _get_hotkey_mode(self):
		try:
			mode = str(
				config.conf["classicSpeech"].get("hotkeyMode", HOTKEY_MODE_BOTH)
			).strip().lower()
		except Exception:
			mode = HOTKEY_MODE_BOTH

		if mode not in {
			HOTKEY_MODE_OFF,
			HOTKEY_MODE_DIALOGS,
			HOTKEY_MODE_MENUS,
			HOTKEY_MODE_BOTH,
		}:
			return HOTKEY_MODE_BOTH
		return mode

	def _hotkey_allowed_in_context(self, context, mode_override=None):
		mode = mode_override if mode_override is not None else self._get_hotkey_mode()

		if mode == HOTKEY_MODE_OFF:
			return False
		if mode == HOTKEY_MODE_BOTH:
			return True
		if mode == HOTKEY_MODE_MENUS:
			return context == "menu"
		if mode == HOTKEY_MODE_DIALOGS:
			return context != "menu"
		return True

	def _apply_hotkey_mode(self, semantic_tokens, context, mode_override=None):
		allow_hotkey = self._hotkey_allowed_in_context(context, mode_override=mode_override)

		if should_debug_log():
			logged_mode = mode_override if mode_override is not None else self._get_hotkey_mode()
			log.debug(
				f"Hotkey filtering: mode={logged_mode}, context={context}, allow={allow_hotkey}"
			)

		if allow_hotkey:
			return semantic_tokens, False

		filtered = []
		removed_hotkey = False
		for token in semantic_tokens:
			if getattr(token, "kind", None) == TOKEN_HOTKEY:
				removed_hotkey = True
				continue
			filtered.append(token)
		return filtered, removed_hotkey

	# -------------------------
	# Hotkey command cleanup
	# -------------------------
	def _strip_hotkey_commands(self, commands, semantic_tokens, removed_hotkey=False):
		has_hotkey = any(token.kind == TOKEN_HOTKEY for token in semantic_tokens)
		if not has_hotkey and not removed_hotkey:
			return commands
		return [c for c in commands if not isinstance(c, CharacterModeCommand)]

	def _get_hotkey_types(self):
		try:
			types_value = str(
				config.conf["classicSpeech"].get("hotkeyTypes", HOTKEY_TYPES_BOTH)
			).strip()
		except Exception:
			types_value = HOTKEY_TYPES_BOTH

		if types_value not in {
			HOTKEY_TYPES_ACCESS,
			HOTKEY_TYPES_COMMAND,
			HOTKEY_TYPES_BOTH,
		}:
			return HOTKEY_TYPES_BOTH
		return types_value

	def _is_access_key_hotkey(self, hotkey_text):
		modifiers, key = self._split_hotkey_parts(hotkey_text)
		if not modifiers and len(str(key).strip()) == 1:
			return True
		lower_mods = [str(mod).strip().lower() for mod in modifiers]
		return lower_mods == ["alt"] and len(str(key).strip()) == 1

	def _hotkey_type_allowed(self, hotkey_text):
		types_value = self._get_hotkey_types()
		if types_value == HOTKEY_TYPES_BOTH:
			return True
		is_access = self._is_access_key_hotkey(hotkey_text)
		if types_value == HOTKEY_TYPES_ACCESS:
			return is_access
		if types_value == HOTKEY_TYPES_COMMAND:
			return not is_access
		return True

	def _apply_hotkey_type_filter(self, semantic_tokens):
		filtered = []
		for tok in semantic_tokens:
			if getattr(tok, "kind", None) != TOKEN_HOTKEY:
				filtered.append(tok)
				continue
			if self._hotkey_type_allowed(tok.text()):
				filtered.append(tok)
		return filtered

	def _get_hotkey_format(self):
		try:
			format_value = str(
				config.conf["classicSpeech"].get("hotkeyFormat", HOTKEY_FORMAT_NATIVE)
			).strip()
		except Exception:
			format_value = HOTKEY_FORMAT_NATIVE

		if format_value not in {
			HOTKEY_FORMAT_NATIVE,
			HOTKEY_FORMAT_EXPANDED_NO_PLUS,
			HOTKEY_FORMAT_ABBREVIATED_NO_PLUS,
		}:
			return HOTKEY_FORMAT_NATIVE
		return format_value

	def _get_dialog_access_key_only(self):
		try:
			return bool(config.conf["classicSpeech"].get("hotkeyDialogAccessKeyOnly", False))
		except Exception:
			return False

	def _split_hotkey_parts(self, hotkey_text):
		text = str(hotkey_text or "").strip()
		if not text:
			return [], ""
		normalized = (
			text.replace(" +", "+")
			.replace("+ ", "+")
			.replace(",", "+")
		)
		while "++" in normalized:
			normalized = normalized.replace("++", "+")
		parts = [part.strip() for part in normalized.split("+") if part.strip()]
		if not parts:
			return [], text
		if len(parts) == 1:
			return [], parts[0]
		return parts[:-1], parts[-1]

	def _format_hotkey_key_name(self, key):
		key = str(key or "").strip()
		if len(key) == 1 and key.isalpha():
			return key.upper()
		return key

	def _format_hotkey_modifier(self, modifier, format_value):
		mod = str(modifier or "").strip()
		lower = mod.lower()
		if lower in {"ctrl", "control"}:
			return "Ctrl" if format_value == HOTKEY_FORMAT_ABBREVIATED_NO_PLUS else "Control"
		if lower in {"alt", "shift", "nvda"}:
			return lower.upper() if lower == "nvda" else lower.capitalize()
		if lower in {"win", "windows"}:
			return "Win" if format_value == HOTKEY_FORMAT_ABBREVIATED_NO_PLUS else "Windows"
		return mod

	def _format_hotkey_text(self, hotkey_text, context):
		text = str(hotkey_text or "").strip()
		if not text:
			return text

		# NVDA can join access key + accelerator key with two spaces, e.g.
		# "Alt, N  Ctrl+N". Format each shortcut independently.
		shortcut_chunks = [chunk.strip() for chunk in text.replace("\u00a0", " ").split("  ") if chunk.strip()]
		if len(shortcut_chunks) > 1:
			return " ".join(
				self._format_hotkey_text(chunk, context) for chunk in shortcut_chunks
			).strip()

		modifiers, key = self._split_hotkey_parts(text)
		if (
			context == "dialog"
			and self._get_dialog_access_key_only()
			and len(modifiers) == 1
			and modifiers[0].strip().lower() == "alt"
			and len(str(key).strip()) == 1
		):
			return self._format_hotkey_key_name(key)

		format_value = self._get_hotkey_format()
		if format_value == HOTKEY_FORMAT_NATIVE:
			return text

		if not modifiers:
			return self._format_hotkey_key_name(key)

		spoken_parts = [
			self._format_hotkey_modifier(mod, format_value) for mod in modifiers
		]
		spoken_parts.append(self._format_hotkey_key_name(key))
		return " ".join(part for part in spoken_parts if part).strip()

	def _apply_hotkey_formatting(self, semantic_tokens, context):
		formatted = []
		for tok in semantic_tokens:
			if getattr(tok, "kind", None) != TOKEN_HOTKEY:
				formatted.append(tok)
				continue
			formatted.append(tok.with_spoken(self._format_hotkey_text(tok.text(), context)))
		return formatted

	# -------------------------
	# Default button speech
	# -------------------------
