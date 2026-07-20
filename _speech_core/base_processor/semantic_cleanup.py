import api
import logHandler

from .debug import should_debug_log

from .context import ROOT_MENU_NAV_MARKER_ROLES
from ..dialog_helpers import object_is_in_dialog
from ..settings.text_processing_config import (
	LIST_ITEM_STATE_REPORTING_BOTH,
	LIST_ITEM_STATE_REPORTING_NATIVE,
	LIST_ITEM_STATE_REPORTING_NONE,
	LIST_ITEM_STATE_REPORTING_NOT_SELECTED,
	LIST_ITEM_STATE_REPORTING_SELECTED,
	_get_list_item_state_reporting_mode,
)
from ..tokens import TOKEN_NAME, TOKEN_ROLE, TOKEN_STATE, TOKEN_VALUE, token

log = logHandler.log


class SemanticCleanup:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _promote_root_menu_role_to_nav_marker(self, semantic_tokens):
		"""
		Popup menus are structural navigation markers, not ordinary verbosity
		role tokens. Drop any role token whose semantic role is exactly "menu"
		after literal review has already bypassed the processor.

		The object name still speaks normally (for example "NVDA" or "Context"),
		but the structural container word "menu" is not formatted as a user-facing
		role. Menubar, menuitem, checkmenuitem, and radiomenuitem roles are left
		untouched.
		"""
		filtered = []
		for semantic_token in semantic_tokens:
			if getattr(semantic_token, "kind", None) != TOKEN_ROLE:
				filtered.append(semantic_token)
				continue

			token_role_key = self._normalize_role_key(getattr(semantic_token, "raw", ""))
			if token_role_key in ROOT_MENU_NAV_MARKER_ROLES:
				continue

			filtered.append(semantic_token)

		return filtered

	def _ensure_menu_context_not_silent(self, built_sequence, semantic_tokens, context):
		if context != "menu":
			return built_sequence
		if any(isinstance(item, str) and item.strip() for item in built_sequence):
			return built_sequence
		if self._get_focus_role_key() in ROOT_MENU_NAV_MARKER_ROLES:
			return ["menu"]
		return built_sequence

	# -------------------------
	# Role validation
	# -------------------------
	def _demote_role_token(self, token):
		text = ""
		if hasattr(token, "text") and callable(token.text):
			text = token.text().strip()
		if not text:
			text = str(
				getattr(token, "spoken", "") or getattr(token, "raw", "") or ""
			).strip()

		raw_value = [text] if text else []
		meta = dict(getattr(token, "meta", {}) or {})
		meta["demotedFromRole"] = True

		if hasattr(token, "clone") and callable(token.clone):
			return token.clone(
				kind=TOKEN_NAME,
				raw=raw_value,
				spoken=text,
				meta=meta,
			)

		token.kind = TOKEN_NAME
		token.raw = raw_value
		token.spoken = text
		token.meta = meta
		return token

	def _promote_editable_combo_role_token(self, token, token_role_key, focus_role_key):
		"""Expose editable combo focus as the single token-editor role "edit combo".

		NVDA can speak File name / combo box / collapsed while focus is the editable
		child of a combo. v30 treated this as editcombo so the role token was useful
		to the token editor instead of being indistinguishable from ordinary combo
		boxes.
		"""
		if token_role_key != "combobox" or focus_role_key != "editabletext":
			return token
		meta = dict(getattr(token, "meta", {}) or {})
		meta["promotedFromRole"] = "combobox"
		if hasattr(token, "clone") and callable(token.clone):
			return token.clone(raw="editcombo", spoken="edit combo", meta=meta)
		token.raw = "editcombo"
		token.spoken = "edit combo"
		token.meta = meta
		return token

	def _validate_roles(self, semantic_tokens):
		focus = api.getFocusObject()
		focus_role_key = self._get_object_role_key(focus)
		if not focus_role_key:
			return semantic_tokens

		in_dialog = object_is_in_dialog(focus) if focus else False

		validated = []
		for token in semantic_tokens:
			if token.kind != TOKEN_ROLE:
				validated.append(token)
				continue

			token_role_key = self._normalize_role_key(getattr(token, "raw", ""))
			token = self._promote_editable_combo_role_token(token, token_role_key, focus_role_key)
			token_role_key = self._normalize_role_key(getattr(token, "raw", ""))

			if self._roles_compatible(token_role_key, focus_role_key):
				validated.append(token)
				continue

			if token_role_key == "dialog" and in_dialog:
				validated.append(token)
				continue

			if should_debug_log():
				token_text = (
					token.text()
					if hasattr(token, "text") and callable(token.text)
					else str(getattr(token, "spoken", "") or getattr(token, "raw", ""))
				)
				log.debug(
					f"Demoting role token '{token_text}' "
					f"(classified={token_role_key}, focus={focus_role_key}, inDialog={in_dialog})"
				)

			validated.append(self._demote_role_token(token))

		return validated


	def _state_text(self, token):
		if getattr(token, "kind", None) != TOKEN_STATE:
			return ""
		text = token.text() if hasattr(token, "text") and callable(token.text) else str(getattr(token, "spoken", "") or getattr(token, "raw", "") or "")
		return text.strip().lower()

	def _selected_state_text(self, token):
		text = self._state_text(token)
		return text if text in {"selected", "not selected"} else ""

	def _is_combo_expansion_state(self, token):
		text = self._state_text(token)
		if text in {"collapsed", "expanded"}:
			return True
		raw = str(getattr(token, "raw", "") or "").strip().lower()
		return raw in {"collapsed", "expanded"}

	def _suppress_combo_expansion_states(self, semantic_tokens):
		"""Drop collapsed/expanded noise only from combo/edit-combo focus speech.

		The token editor should still own the state token globally. Keep this tied
		to sequences that include a combo role token; state-only change speech from
		Alt+Down/Alt+Up should continue to report expanded/collapsed natively.
		"""
		combo_roles = {"combobox", "editcombo"}
		has_combo_role = any(
			getattr(tok, "kind", None) == TOKEN_ROLE
			and self._normalize_role_key(getattr(tok, "raw", "")) in combo_roles
			for tok in semantic_tokens
		)
		if not has_combo_role:
			return semantic_tokens
		return [tok for tok in semantic_tokens if not self._is_combo_expansion_state(tok)]

	def _list_item_state_allowed(self, state_text, reporting_mode):
		if reporting_mode == LIST_ITEM_STATE_REPORTING_NATIVE:
			return True
		if reporting_mode == LIST_ITEM_STATE_REPORTING_NONE:
			return False
		if reporting_mode == LIST_ITEM_STATE_REPORTING_BOTH:
			return True
		if reporting_mode == LIST_ITEM_STATE_REPORTING_SELECTED:
			return state_text == "selected"
		# Default: match the original spec's "Say Not Selected" behavior.
		return state_text == "not selected"

	def _ensure_list_item_state_change_has_value(self, semantic_tokens):
		"""Add focused item text to state-only list item selection changes.

		NVDA state-change speech for Space/toggle selection can be just
		"selected"/"not selected". If ClassicSpeech filters the state, for
		example with "Say not selected", selecting an item becomes silent. Keep
		this narrow to item-like focus and state-only sequences so ordinary focus
		speech and token-editor ordering stay unchanged.
		"""
		focus_role_key = self._get_focus_role_key()
		if focus_role_key not in {"listitem", "treeviewitem", "tablerow", "tablecell"}:
			return semantic_tokens
		if any(getattr(tok, "kind", None) in {TOKEN_NAME, TOKEN_VALUE, TOKEN_ROLE} for tok in semantic_tokens):
			return semantic_tokens
		if not any(self._selected_state_text(tok) for tok in semantic_tokens):
			return semantic_tokens

		focus = api.getFocusObject()
		item_text = ""
		for attr in ("name", "value"):
			try:
				value = getattr(focus, attr, "")
			except Exception:
				value = ""
			value = str(value or "").strip()
			if value:
				item_text = value
				break
		if not item_text:
			return semantic_tokens

		return [token(TOKEN_VALUE, raw=item_text, spoken=item_text)] + list(semantic_tokens)

	def _restore_native_item_state_order(self, semantic_tokens):
		"""Apply list-item selected/not-selected reporting and placement.

		ClassicSpeech only owns which list-item state words should speak.
		Token order remains the token editor's job. Keep this narrow to item-like focus so unrelated
		states such as checked, expanded, or default are not affected.
		"""
		focus_role_key = self._get_focus_role_key()
		if focus_role_key not in {
			"listitem",
			"treeviewitem",
			"menuitem",
			"checkmenuitem",
			"radiomenuitem",
			"tablerow",
			"tablecell",
		}:
			return semantic_tokens

		reporting_mode = _get_list_item_state_reporting_mode()
		if reporting_mode == LIST_ITEM_STATE_REPORTING_NATIVE:
			return semantic_tokens
		restored = []
		for tok in semantic_tokens:
			state_text = self._selected_state_text(tok)
			if state_text:
				if not self._list_item_state_allowed(state_text, reporting_mode):
					continue
				restored.append(tok)
				continue
			restored.append(tok)
		return restored

	def _normalize_item_name_token_to_value(self, semantic_tokens):
		"""Treat item labels as item text/value in the internal token model.

		Accessibility APIs normally expose list/tree/menu item labels as the
		object name. For ClassicSpeech formatting, that text behaves more like
		the current item value/content than a container/control name. Keep this
		narrow to item-like focused roles so buttons, dialogs, check boxes, and
		labeled fields continue to use name normally.
		"""
		focus_role_key = self._get_focus_role_key()
		if focus_role_key not in {
			"listitem",
			"treeviewitem",
			"menuitem",
			"checkmenuitem",
			"radiomenuitem",
			"tablerow",
			"tablecell",
		}:
			return semantic_tokens

		# If there is already a value token, leave the sequence alone. This avoids
		# smashing merged container speech such as Categories/list/General where
		# the focused item already classified as value because it followed a role.
		if any(getattr(tok, "kind", None) == TOKEN_VALUE for tok in semantic_tokens):
			return semantic_tokens

		normalized = []
		converted = False
		for tok in semantic_tokens:
			if not converted and getattr(tok, "kind", None) == TOKEN_NAME:
				text = tok.text() if hasattr(tok, "text") and callable(tok.text) else str(getattr(tok, "spoken", "") or "")
				meta = dict(getattr(tok, "meta", {}) or {})
				meta["itemNamePromotedToValue"] = True
				if hasattr(tok, "clone") and callable(tok.clone):
					normalized.append(tok.clone(kind=TOKEN_VALUE, spoken=text, meta=meta))
				else:
					tok.kind = TOKEN_VALUE
					tok.spoken = text
					tok.meta = meta
					normalized.append(tok)
				converted = True
				continue
			normalized.append(tok)
		return normalized

	# -------------------------
	# Position mode
	# -------------------------
