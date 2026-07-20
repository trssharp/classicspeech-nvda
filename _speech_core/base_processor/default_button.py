import api

from ..dialog_helpers import focused_button_default_status
from ..tokens import TOKEN_ROLE, TOKEN_STATE, token


class DefaultButtonTokenInserter:
	def __init__(self, owner):
		self.owner = owner

	def __getattr__(self, name):
		return getattr(self.owner, name)

	def _role_order_index_for_default_token(self):
		try:
			profile = self.verbosity.get_profile_config()
			order = profile.get("order", []) if isinstance(profile, dict) else []
			if TOKEN_ROLE in order:
				return int(order.index(TOKEN_ROLE))
		except Exception:
			pass
		return 1

	def _insert_focused_default_button_token(self, semantic_tokens, focus=None):
		"""Insert a speakable default-state token before role for the focused default button.

		This intentionally announces only when focus lands on the default button:
		``OK, default, button``.  It does not announce the dialog default merely
		because a dialog opened.
		"""
		try:
			if not bool(getattr(self.verbosity, "announce_default_button", False)):
				return semantic_tokens
		except Exception:
			return semantic_tokens

		focus = focus or api.getFocusObject()
		try:
			is_button, is_default, _default_name = focused_button_default_status(focus)
		except Exception:
			return semantic_tokens

		if not is_button or not is_default:
			return semantic_tokens

		# Avoid duplicate default tokens if a future NVDA/core sequence exposes one.
		for tok in semantic_tokens or []:
			if getattr(tok, "kind", None) != TOKEN_STATE:
				continue
			try:
				if tok.text().strip().lower() == "default":
					return semantic_tokens
			except Exception:
				continue

		default_tok = token(
			TOKEN_STATE,
			raw="default",
			spoken="default",
			source=[],
			meta={
				"orderIndex": self._role_order_index_for_default_token(),
				"suppressRename": True,
				"suppressProfileLabelMute": True,
			},
		)

		# Only decorate actual focused-button description sequences.
		# Action-only messages such as ``pressed`` arrive while focus is still
		# on the default button, but they should not become ``default pressed``.
		has_button_role = False
		for tok in semantic_tokens or []:
			if getattr(tok, "kind", None) != TOKEN_ROLE:
				continue
			try:
				if tok.text().strip().lower() == "button":
					has_button_role = True
					break
			except Exception:
				continue

		if not has_button_role:
			return semantic_tokens

		result = []
		inserted = False
		for tok in semantic_tokens:
			if not inserted and getattr(tok, "kind", None) == TOKEN_ROLE:
				result.append(default_tok)
				inserted = True
			result.append(tok)

		return result

	# -------------------------
	# Main processing
	# -------------------------
