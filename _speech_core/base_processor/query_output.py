import speech

from ..settings import HOTKEY_MODE_BOTH, POSITION_MODE_EACH, POSITION_MODE_OFF
from ..token_policy import apply_token_policy
from ..tokens import (
	TOKEN_DESCRIPTION,
	TOKEN_HOTKEY,
	TOKEN_NAME,
	TOKEN_POSITION,
	TOKEN_ROLE,
	TOKEN_STATE,
	TOKEN_VALUE,
	clone_tokens,
	token,
)


class QueryOutputBuilder:
	def __init__(self, owner):
		self.owner = owner
		self._query_memory_focus_signature = None
		self._query_memory_focus_tokens = None
		self._query_memory_context_tokens = []
		self._query_memory_context = None

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _reset_query_memory(self, focus_signature=None):
		self._query_memory_focus_signature = focus_signature

	def _token_text_key(self, semantic_token):
		kind = getattr(semantic_token, "kind", "")
		text = ""
		if hasattr(semantic_token, "text") and callable(semantic_token.text):
			text = semantic_token.text().strip().lower()
		return (kind, text)

	def _append_unique_tokens(self, target_tokens, new_tokens):
		seen = {self._token_text_key(tok) for tok in target_tokens}
		for semantic_token in new_tokens or []:
			key = self._token_text_key(semantic_token)
			if key in seen:
				continue
			seen.add(key)
			target_tokens.append(semantic_token.clone())
		return target_tokens

	def _semantic_tokens_contain_focus_name(self, semantic_tokens, focus):
		focus_name = self._safe_obj_str_attr(focus, "name", "")
		if not focus_name:
			return False
		focus_name = focus_name.strip().lower()
		for semantic_token in semantic_tokens or []:
			if getattr(semantic_token, "kind", None) != TOKEN_NAME:
				continue
			text = semantic_token.text().strip().lower()
			if text == focus_name:
				return True
		return False

	def _semantic_tokens_look_like_context(self, semantic_tokens, focus):
		if not semantic_tokens:
			return False
		if self._semantic_tokens_contain_focus_name(semantic_tokens, focus):
			return False

		kinds = {getattr(tok, "kind", None) for tok in semantic_tokens}
		if TOKEN_ROLE in kinds:
			return True
		if TOKEN_POSITION in kinds:
			return True
		return False

	def _remember_query_semantic_tokens(self, semantic_tokens, context):
		# v28: disabled. Insert+Tab now rebuilds directly from the configured
		# object (focus by default, navigator if selected) instead of accumulating
		# fragments from previous speech. This prevents object-navigation moves from
		# stacking position/context tokens into later query output.
		return

	def _get_query_memory_tokens_for_object(self, obj):
		return None

	def _query_has_kind(self, semantic_tokens, kind):
		return any(getattr(tok, "kind", None) == kind for tok in semantic_tokens or [])

	def _query_has_text(self, semantic_tokens, text):
		needle = str(text or "").strip().lower()
		if not needle:
			return False
		for tok in semantic_tokens or []:
			try:
				if tok.text().strip().lower() == needle:
					return True
			except Exception:
				continue
		return False

	def _augment_semantic_tokens_from_focus_object(self, semantic_tokens, obj, profile_config=None):
		if not obj:
			return semantic_tokens

		profile_config = profile_config or self.verbosity.get_profile_config()
		enabled = dict((profile_config or {}).get("enabledTokens", {}))
		role_key = self._get_object_role_key(obj)

		if role_key not in {"editabletext", "document"}:
			if enabled.get(TOKEN_DESCRIPTION, True) and not self._query_has_kind(semantic_tokens, TOKEN_DESCRIPTION):
				description = self._safe_description_text(obj)
				if description and not self._query_has_text(semantic_tokens, description):
					semantic_tokens.append(token(TOKEN_DESCRIPTION, raw=description, spoken=description, source=[description]))


		return semantic_tokens

	def _build_query_tokens_from_beginner_slots(self, obj, remembered_tokens, query_profile_config, query_behavior):
		base_tokens = clone_tokens(remembered_tokens or [])
		enabled = dict((query_profile_config or {}).get("enabledTokens", {}))

		if enabled.get(TOKEN_NAME, True) and not self._query_has_kind(base_tokens, TOKEN_NAME):
			name = self._safe_obj_str_attr(obj, "name", "")
			if name:
				base_tokens.append(token(TOKEN_NAME, raw=[name], spoken=name, source=[name]))

		if enabled.get(TOKEN_ROLE, True) and not self._query_has_kind(base_tokens, TOKEN_ROLE):
			role_text = self._safe_role_text(obj)
			role_key = self._get_object_role_key(obj)
			if role_text:
				base_tokens.append(
					token(TOKEN_ROLE, raw=role_key or role_text, spoken=role_text, source=[role_text])
				)

		if enabled.get(TOKEN_STATE, True) and not self._query_has_kind(base_tokens, TOKEN_STATE):
			base_tokens.extend(self._safe_state_tokens(obj))

		if enabled.get(TOKEN_VALUE, True) and not self._query_has_kind(base_tokens, TOKEN_VALUE):
			value = self._safe_value_text(obj)
			if value:
				base_tokens.append(token(TOKEN_VALUE, raw=value, spoken=value, source=[value]))

		position_mode = (query_behavior or {}).get("positionMode", POSITION_MODE_EACH)
		if (
			enabled.get(TOKEN_POSITION, True)
			and position_mode != POSITION_MODE_OFF
			and not self._query_has_kind(base_tokens, TOKEN_POSITION)
		):
			position = self._safe_position_text(obj)
			if position:
				base_tokens.append(token(TOKEN_POSITION, raw=position, spoken=position, source=[position]))

		if not self._query_has_kind(base_tokens, TOKEN_HOTKEY):
			hotkey = self._safe_hotkey_text(obj)
			if hotkey:
				base_tokens.append(token(TOKEN_HOTKEY, raw=hotkey, spoken=hotkey, source=[hotkey]))

		if enabled.get(TOKEN_DESCRIPTION, True) and not self._query_has_kind(base_tokens, TOKEN_DESCRIPTION):
			description = self._safe_description_text(obj)
			if description and not self._query_has_text(base_tokens, description):
				base_tokens.append(token(TOKEN_DESCRIPTION, raw=description, spoken=description, source=[description]))


		return base_tokens

	def _build_query_output(self, obj):
		if not obj:
			return [], ""

		remembered_tokens = self._get_query_memory_tokens_for_object(obj) or []
		query_profile_config = self.verbosity.get_query_profile_config()
		query_behavior = self.verbosity.get_query_behavior()
		semantic_tokens = self._build_query_tokens_from_beginner_slots(
			obj,
			remembered_tokens,
			query_profile_config,
			query_behavior,
		)
		semantic_tokens = self._augment_semantic_tokens_from_focus_object(semantic_tokens, obj, query_profile_config)
		if not semantic_tokens:
			return [], ""

		context = self._get_focus_context()
		query_position_mode = query_behavior.get("positionMode", POSITION_MODE_EACH)
		query_hotkey_mode = HOTKEY_MODE_BOTH

		semantic_tokens = self._promote_root_menu_role_to_nav_marker(semantic_tokens)
		semantic_tokens = self._validate_roles(semantic_tokens)
		semantic_tokens = self._apply_position_mode(semantic_tokens, mode_override=query_position_mode)
		semantic_tokens, _removed_hotkey = self._apply_hotkey_mode(
			semantic_tokens,
			context,
			mode_override=query_hotkey_mode,
		)
		semantic_tokens = self._apply_hotkey_type_filter(semantic_tokens)
		semantic_tokens = self._apply_hotkey_formatting(semantic_tokens, context)

		semantic_tokens, _pending_hotkey = apply_token_policy(
			semantic_tokens,
			context=context,
			focus_role_key=self._get_object_role_key(obj),
			pending_hotkey=None,
			suppress_editable_text_value=False,
		)

		built = self.formatter.format(
			semantic_tokens,
			profile_config=query_profile_config,
		)
		text_parts = [part.strip() for part in built if isinstance(part, str) and part.strip()]
		text = " ".join(text_parts).strip()
		return built, text

	def get_query_object_text(self, obj):
		_built, text = self._build_query_output(obj)
		return text

	def speak_query_object(self, obj):
		if not obj:
			return

		built, _text = self._build_query_output(obj)
		if built:
			self.owner._bypass_next_sequence = True
			speech.speak(built)

	def speak_current_hotkey(self, obj):
		"""Speak the current object's shortcut as an explicit user command.

		This intentionally bypasses normal hotkey-mode filtering. Automatic
		hotkey speech obeys the Hotkeys panel, but the say-shortcut command
		should always answer when NVDA exposes a shortcut for the focused object.
		"""
		hotkey = self._safe_hotkey_text(obj)
		if not hotkey:
			return False
		self.owner._bypass_next_sequence = True
		speech.speak([hotkey])
		return True

