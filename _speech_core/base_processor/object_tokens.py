import logHandler

from .debug import should_debug_log
import textInfos

from .context import QUERY_SAFE_STATE_NAMES
from ..tokens import (
	TOKEN_DESCRIPTION,
	TOKEN_HOTKEY,
	TOKEN_NAME,
	TOKEN_POSITION,
	TOKEN_ROLE,
	TOKEN_STATE,
	TOKEN_VALUE,
	token,
)

log = logHandler.log


class ObjectTokenBuilder:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _safe_obj_attr(self, obj, attr_name, default=None):
		if not obj:
			return default
		try:
			return getattr(obj, attr_name, default)
		except Exception as e:
			if should_debug_log():
				log.debug(
					f"Safe object attribute read failed for {attr_name}: {e}"
				)
			return default

	def _safe_obj_str_attr(self, obj, attr_name, default=""):
		value = self._safe_obj_attr(obj, attr_name, default)
		if value is None:
			return default
		try:
			return str(value).strip()
		except Exception as e:
			if should_debug_log():
				log.debug(
					f"Safe object string conversion failed for {attr_name}: {e}"
				)
			return default


	def _safe_selected_text(self, obj):
		if not obj:
			return ""
		try:
			make_text_info = getattr(obj, "makeTextInfo", None)
			if not callable(make_text_info):
				return ""
			info = make_text_info(textInfos.POSITION_SELECTION)
			if getattr(info, "isCollapsed", False):
				return ""
			text = getattr(info, "text", "")
			if text is None:
				return ""
			return str(text).strip()
		except Exception as e:
			if should_debug_log():
				log.debug(f"Selected text lookup failed: {e}")
			return ""

	def _safe_role_text(self, obj):
		role = self._safe_obj_attr(obj, "role", None)
		if role is None:
			return ""
		try:
			display = getattr(role, "displayString", None)
			if display:
				return str(display).strip()
		except Exception:
			pass
		role_name = getattr(role, "name", None)
		if role_name:
			return str(role_name).replace("_", " ").strip().lower()
		return self._normalize_role_key(role) or ""

	def _safe_state_tokens(self, obj):
		states = self._safe_obj_attr(obj, "states", None)
		role_key = self._get_object_role_key(obj)
		if not states:
			if role_key == "checkbox":
				return [token(TOKEN_STATE, raw="not checked", spoken="not checked", source=["not checked"])]
			return []

		state_tokens = []
		seen = set()
		all_state_names = set()
		for state in states:
			try:
				state_name = str(getattr(state, "name", state)).strip().lower()
			except Exception:
				continue
			if state_name:
				all_state_names.add(state_name)
			if not state_name or state_name not in QUERY_SAFE_STATE_NAMES:
				continue
			if state_name in seen:
				continue
			seen.add(state_name)

			spoken = ""
			try:
				display = getattr(state, "displayString", None)
				if display:
					spoken = str(display).strip()
			except Exception:
				spoken = ""
			if not spoken:
				spoken = state_name.replace("_", " ")

			state_tokens.append(
				token(TOKEN_STATE, raw=state_name, spoken=spoken, source=[spoken])
			)

		if role_key == "checkbox" and "checked" not in all_state_names and "halfchecked" not in all_state_names:
			state_tokens.append(
				token(TOKEN_STATE, raw="not checked", spoken="not checked", source=["not checked"])
			)

		# Native NVDA can speak the negative selected state ("not selected") for
		# selectable items even though the object state set only exposes SELECTABLE,
		# not a separate NOT_SELECTED state. Since v28 navigator-query speech is rebuilt
		# from the navigator object instead of remembered speech fragments, synthesize
		# that same user-facing state here so Insert+Tab matches object navigation.
		if (
			"selectable" in all_state_names
			and "selected" not in all_state_names
			and role_key in {
				"listitem",
				"treeviewitem",
				"menuitem",
				"checkmenuitem",
				"radiomenuitem",
				"tablerow",
				"tablecell",
			}
		):
			state_tokens.append(
				token(TOKEN_STATE, raw="not selected", spoken="not selected", source=["not selected"])
			)

		return state_tokens

	def _safe_position_text(self, obj):
		position_info = self._safe_obj_attr(obj, "positionInfo", None)
		if not isinstance(position_info, dict):
			return ""

		index = position_info.get("indexInGroup")
		similar = position_info.get("similarItemsInGroup")
		if index and similar:
			return f"{index} of {similar}"
		return ""

	def _safe_hotkey_text(self, obj):
		for attr_name in ("keyboardShortcut", "shortcut", "keyBinding"):
			text = self._safe_obj_str_attr(obj, attr_name, "")
			if text:
				return text
		return ""

	def _safe_description_text(self, obj):
		for attr_name in ("description", "helpText", "help", "displayDescription"):
			text = self._safe_obj_str_attr(obj, attr_name, "")
			if text:
				return text
		return ""

	def _safe_tooltip_text(self, obj):
		for attr_name in ("toolTipText", "tooltipText", "toolTip", "tooltip"):
			text = self._safe_obj_str_attr(obj, attr_name, "")
			if text:
				return text
		return ""

	def _safe_value_text(self, obj):
		value = self._safe_obj_attr(obj, "value", None)
		if value is None:
			return ""
		try:
			return str(value).strip()
		except Exception:
			return ""

	def _build_query_tokens_for_object(self, obj):
		semantic_tokens = []

		name = self._safe_obj_str_attr(obj, "name", "")
		if name:
			semantic_tokens.append(token(TOKEN_NAME, raw=[name], spoken=name, source=[name]))

		value = self._safe_value_text(obj)
		if value:
			semantic_tokens.append(token(TOKEN_VALUE, raw=value, spoken=value, source=[value]))

		role_text = self._safe_role_text(obj)
		role_key = self._get_object_role_key(obj)
		if role_text:
			semantic_tokens.append(
				token(
					TOKEN_ROLE,
					raw=role_key or role_text,
					spoken=role_text,
					source=[role_text],
				)
			)

		semantic_tokens.extend(self._safe_state_tokens(obj))

		position = self._safe_position_text(obj)
		if position:
			semantic_tokens.append(
				token(TOKEN_POSITION, raw=position, spoken=position, source=[position])
			)

		hotkey = self._safe_hotkey_text(obj)
		if hotkey:
			semantic_tokens.append(
				token(TOKEN_HOTKEY, raw=hotkey, spoken=hotkey, source=[hotkey])
			)

		description = self._safe_description_text(obj)
		if description:
			semantic_tokens.append(
				token(TOKEN_DESCRIPTION, raw=description, spoken=description, source=[description])
			)


		return semantic_tokens

