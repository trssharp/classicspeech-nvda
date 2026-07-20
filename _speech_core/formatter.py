# _speech_core/formatter.py

from speech.commands import BreakCommand
import logHandler

from .prosody_routing import (
	focus_navigation_prosody_commands,
	profile_id_for_formatter_origin,
	review_object_navigation_prosody_commands,
	system_notification_prosody_commands,
	wrap_profile_sequence,
)
from .tokens import (
	TOKEN_NAME,
	TOKEN_ROLE,
	TOKEN_VALUE,
	TOKEN_STATE,
	TOKEN_POSITION,
	TOKEN_DESCRIPTION,
	TOKEN_TOOLTIP,
	TOKEN_HOTKEY,
	DEFAULT_TOKEN_ORDER,
	TOKEN_KIND_SET,
	coerce_tokens,
)

log = logHandler.log
DEBUG = False


RENAMEABLE_TOKEN_KINDS = {
	TOKEN_ROLE,
	TOKEN_STATE,
}

MUTEABLE_LABEL_TOKEN_KINDS = {
	TOKEN_ROLE,
	TOKEN_STATE,
}


DEFAULT_ENABLED_TOKENS = {
	TOKEN_NAME: True,
	TOKEN_ROLE: True,
	TOKEN_VALUE: True,
	TOKEN_STATE: True,
	TOKEN_POSITION: True,
	TOKEN_DESCRIPTION: True,
	TOKEN_TOOLTIP: False,
	TOKEN_HOTKEY: True,
}


DEFAULT_PAUSES = {
	TOKEN_NAME: -1,
	TOKEN_ROLE: -1,
	TOKEN_VALUE: -1,
	TOKEN_STATE: -1,
	TOKEN_POSITION: -1,
	TOKEN_DESCRIPTION: -1,
	TOKEN_TOOLTIP: -1,
	TOKEN_HOTKEY: -1,
}


DEFAULT_PAUSE_AFTER_FINAL_TOKEN = True
DEFAULT_PAUSE_PLACEMENT = "before"


class SpeechFormatter:
	"""
	Formats structured speech tokens into a final NVDA speech sequence.

	Ownership:
	- formatter owns filtering, ordering, renames, mutedLabels, pauses,
	  and final rendering
	- token_policy owns keep/defer token behavior
	- classifier owns semantic token creation
	"""

	def __init__(self, verbosityManager=None):
		self.verbosityManager = verbosityManager

	def format(self, tokens, profile_config=None, speech_origin="focus"):
		"""
		Main entry point.

		@param tokens: iterable of SpeechToken / dict-like token records
		@param profile_config: optional profile config dict. If omitted,
			current config from verbosityManager will be used.
		@param speech_origin: ``"objectNavigation"`` only for a recognized,
			enabled NVDA navigator-object script; otherwise the focus default.
		@return: list suitable for speech.speak()
		"""
		tokens = coerce_tokens(tokens)
		profile = self._normalize_profile_config(
			self._resolve_profile_config(profile_config)
		)

		filtered_tokens = self._filter_enabled(tokens, profile)
		ordered_tokens = self._apply_order(filtered_tokens, profile)
		renamed_tokens = self._apply_renames(ordered_tokens, profile)
		sequence = self._build_routed_sequence(renamed_tokens, profile, speech_origin=speech_origin)

		if DEBUG:
			try:
				log.debug(f"SpeechFormatter input tokens: {[t.as_dict() for t in tokens]}")
			except Exception:
				pass
			log.debug(f"SpeechFormatter normalized profile: {profile}")
			log.debug(
				f"SpeechFormatter output sequence: "
				f"{[str(item) for item in sequence]}"
			)

		return sequence

	# =====================
	# Profile helpers
	# =====================

	def _resolve_profile_config(self, profile_config):
		if isinstance(profile_config, dict):
			return profile_config

		if self.verbosityManager is not None:
			try:
				return self.verbosityManager.get_profile_config()
			except Exception:
				log.exception("SpeechFormatter failed to fetch profile config")

		return {
			"enabledTokens": dict(DEFAULT_ENABLED_TOKENS),
			"pauseMode": "global",
			"globalPause": 80,
			"order": list(DEFAULT_TOKEN_ORDER),
			"renames": {},
			"mutedLabels": [],
			"pauses": dict(DEFAULT_PAUSES),
			"pauseAfterFinalToken": DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
			"pausePlacement": DEFAULT_PAUSE_PLACEMENT,
		}

	def _normalize_profile_config(self, profile_config):
		base = {
			"enabledTokens": dict(DEFAULT_ENABLED_TOKENS),
			"pauseMode": "global",
			"globalPause": 80,
			"order": list(DEFAULT_TOKEN_ORDER),
			"renames": {},
			"mutedLabels": [],
			"pauses": dict(DEFAULT_PAUSES),
			"pauseAfterFinalToken": DEFAULT_PAUSE_AFTER_FINAL_TOKEN,
			"pausePlacement": DEFAULT_PAUSE_PLACEMENT,
		}

		if not isinstance(profile_config, dict):
			return base

		enabled = profile_config.get("enabledTokens", {})
		if isinstance(enabled, dict):
			for kind, value in enabled.items():
				if kind in TOKEN_KIND_SET:
					base["enabledTokens"][kind] = bool(value)

		base["enabledTokens"][TOKEN_POSITION] = True

		pause_mode = str(profile_config.get("pauseMode", "global"))
		if pause_mode not in {"global", "perToken"}:
			pause_mode = "global"
		base["pauseMode"] = pause_mode

		try:
			base["globalPause"] = max(0, int(profile_config.get("globalPause", 80)))
		except (TypeError, ValueError):
			base["globalPause"] = 80

		order = profile_config.get("order")
		if isinstance(order, list):
			cleaned_order = []
			seen = set()
			for kind in order:
				if kind in TOKEN_KIND_SET and kind not in seen:
					cleaned_order.append(kind)
					seen.add(kind)
			for kind in DEFAULT_TOKEN_ORDER:
				if kind not in seen:
					cleaned_order.append(kind)
			base["order"] = cleaned_order

		renames = profile_config.get("renames", {})
		if isinstance(renames, dict):
			clean_renames = {}
			for key, value in renames.items():
				if key is None:
					continue
				key_text = str(key).strip()
				if not key_text:
					continue
				clean_renames[key_text] = str(value)
			base["renames"] = clean_renames

		muted_labels = profile_config.get("mutedLabels", [])
		if isinstance(muted_labels, (list, tuple, set)):
			clean_muted = []
			seen = set()
			for label in muted_labels:
				if label is None:
					continue
				text = str(label).strip()
				if not text:
					continue
				key = text.lower()
				if key in seen:
					continue
				seen.add(key)
				clean_muted.append(text)
			base["mutedLabels"] = clean_muted

		pauses = profile_config.get("pauses", {})
		if isinstance(pauses, dict):
			for kind, value in pauses.items():
				if kind not in TOKEN_KIND_SET:
					continue
				try:
					base["pauses"][kind] = max(-1, int(value))
				except (TypeError, ValueError):
					pass

		if "pauseAfterFinalToken" in profile_config:
			base["pauseAfterFinalToken"] = bool(
				profile_config.get("pauseAfterFinalToken")
			)

		pause_placement = str(profile_config.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT))
		if pause_placement not in {"after", "before"}:
			pause_placement = DEFAULT_PAUSE_PLACEMENT
		base["pausePlacement"] = pause_placement

		return base

	# =====================
	# Filtering
	# =====================

	def _filter_enabled(self, tokens, profile):
		enabled_map = profile.get("enabledTokens", {})
		muted_labels = self._build_muted_label_set(profile)
		result = []

		for token in tokens:
			if token is None or token.is_empty():
				continue

			if self._is_token_explicitly_muted(token):
				continue

			enabled = enabled_map.get(token.kind, True)
			if not enabled:
				continue

			if self._is_token_muted_by_profile_label(token, muted_labels):
				continue

			result.append(token)

		return result

	def _is_token_explicitly_muted(self, token):
		meta = getattr(token, "meta", None) or {}
		if "enabled" in meta:
			return not bool(meta["enabled"])
		if "muted" in meta:
			return bool(meta["muted"])
		return False

	def _build_muted_label_set(self, profile):
		muted_labels = profile.get("mutedLabels", [])
		if not muted_labels:
			return set()

		result = set()
		for label in muted_labels:
			text = str(label).strip().lower()
			if text:
				result.add(text)
		return result

	def _is_token_muted_by_profile_label(self, token, muted_labels):
		if not muted_labels:
			return False

		if token.kind not in MUTEABLE_LABEL_TOKEN_KINDS:
			return False

		meta = getattr(token, "meta", None) or {}
		if bool(meta.get("suppressProfileLabelMute", False)):
			return False

		candidates = []

		spoken_text = token.text().strip()
		if spoken_text:
			candidates.append(spoken_text)

		raw = getattr(token, "raw", None)
		raw_text = self._normalize_candidate(raw)
		if raw_text:
			candidates.append(raw_text)

		seen = set()
		for candidate in candidates:
			key = candidate.lower()
			if key in seen:
				continue
			seen.add(key)
			if key in muted_labels:
				return True

		return False

	# =====================
	# Ordering
	# =====================

	def _apply_order(self, tokens, profile):
		order = profile.get("order", DEFAULT_TOKEN_ORDER)
		order_index = {kind: index for index, kind in enumerate(order)}

		indexed_tokens = list(enumerate(tokens))
		indexed_tokens.sort(
			key=lambda pair: (
				self._get_order_index(pair[1], order_index, len(order)),
				pair[0],
			)
		)
		return [token for _, token in indexed_tokens]

	def _get_order_index(self, token, order_index, default_index):
		meta = getattr(token, "meta", None) or {}

		if "orderIndex" in meta:
			try:
				return int(meta["orderIndex"])
			except (TypeError, ValueError):
				pass

		if "forceLast" in meta and bool(meta["forceLast"]):
			return default_index + 1000

		return order_index.get(token.kind, default_index)

	# =====================
	# Renames
	# =====================

	def _apply_renames(self, tokens, profile):
		renames = profile.get("renames", {})
		if not isinstance(renames, dict) or not renames:
			return tokens

		lower_map = {
			str(key).strip().lower(): str(value)
			for key, value in renames.items()
			if str(key).strip()
		}

		result = []
		for token in tokens:
			if token.kind not in RENAMEABLE_TOKEN_KINDS:
				result.append(token)
				continue

			if self._token_blocks_profile_rename(token):
				result.append(token)
				continue

			replacement = self._find_token_rename(token, renames, lower_map)
			if replacement is None:
				result.append(token)
			else:
				result.append(token.with_spoken(replacement))

		return result

	def _token_blocks_profile_rename(self, token):
		meta = getattr(token, "meta", None) or {}
		return bool(meta.get("suppressRename", False))

	def _find_token_rename(self, token, renames, lower_map):
		"""
		Find a rename for a semantic token.

		For role/state tokens, prefer the concrete spoken label first,
		then fall back to semantic identity (token.raw). This lets explicit
		rules like "not checked -> off" win over broader semantic aliases
		like "checked -> on".
		"""
		candidates = []

		spoken_text = token.text().strip()
		if spoken_text:
			candidates.append(spoken_text)

		raw = getattr(token, "raw", None)
		raw_text = self._normalize_candidate(raw)
		if raw_text:
			candidates.append(raw_text)

		seen = set()
		for candidate in candidates:
			candidate_key = candidate.lower()
			if candidate_key in seen:
				continue
			seen.add(candidate_key)

			if candidate in renames:
				return str(renames[candidate])

			if candidate_key in lower_map:
				return lower_map[candidate_key]

		return None

	def _normalize_candidate(self, value):
		if value is None:
			return ""

		if isinstance(value, (list, tuple)):
			parts = [str(part).strip() for part in value if str(part).strip()]
			return " ".join(parts).strip()

		return str(value).strip()

	# =====================
	# Final sequence
	# =====================

	def _build_routed_sequence(self, tokens, profile, speech_origin="focus"):
		"""Group semantic tokens into safe full-profile queue transactions."""
		owner = profile_id_for_formatter_origin(speech_origin)
		if owner != "focusNavigation":
			return wrap_profile_sequence(
				self._build_sequence(tokens, profile, speech_origin),
				owner, fallback_prosody=False,
			)
		spoken = [token for token in tokens if token.text().strip()]
		if not spoken:
			return []
		groups = []
		current_kind = None
		current = []
		for index, token in enumerate(spoken):
			route = "systemNotifications" if token.kind in {TOKEN_POSITION, TOKEN_HOTKEY} else "focusNavigation"
			if current and route != current_kind:
				groups.append((current_kind, current))
				current = []
			current_kind = route
			current.append(token)
		if current:
			groups.append((current_kind, current))
		sequence = []
		for group_index, (route, group) in enumerate(groups):
		    group_profile = dict(profile)
		    group_profile["pauseAfterFinalToken"] = bool(profile.get("pauseAfterFinalToken", True)) and group_index == len(groups) - 1
		    group_sequence = self._build_sequence(group, group_profile, speech_origin)
		    # A split System group is not the first token of the original
		    # announcement. Preserve the configured before-token pause at this
		    # boundary, and wrap it with the System transaction below.
		    if group_index and str(profile.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT)) == "before":
		        leading_pause = self._get_pause_for_token(group[0], profile, profile.get("pauses", {}))
		        if leading_pause > 0:
		            group_sequence.insert(0, BreakCommand(time=leading_pause))
		    sequence.extend(wrap_profile_sequence(
		        group_sequence, route, fallback_prosody=False,
		    ))
		return sequence

	def _build_sequence(self, tokens, profile, speech_origin="focus"):
		pauses = profile.get("pauses", {})
		pause_after_final = bool(
			profile.get("pauseAfterFinalToken", DEFAULT_PAUSE_AFTER_FINAL_TOKEN)
		)
		pause_placement = str(profile.get("pausePlacement", DEFAULT_PAUSE_PLACEMENT))
		if pause_placement not in {"after", "before"}:
			pause_placement = DEFAULT_PAUSE_PLACEMENT
		sequence = []

		spoken_tokens = []
		for token in tokens:
			text = token.text().strip()
			if text:
				spoken_tokens.append(token)

		for index, token in enumerate(spoken_tokens):
			text = token.text().strip()
			pause = self._get_pause_for_token(token, profile, pauses)
			is_first = index == 0
			is_last = index == len(spoken_tokens) - 1

			if pause_placement == "before" and pause > 0 and not is_first:
				sequence.append(BreakCommand(time=pause))

			# Complete formatter output is owned by the one profile transaction added
			# by ``format``. Do not inject token-scoped prosody inside it: that
			# would duplicate Rate/Pitch/Volume and bypass the direct transaction.
			sequence.append(text)

			# In after-token placement, pauses between tokens are owned by the
			# preceding token. The final-token option controls the trailing pause.
			if pause_placement == "after" and pause > 0 and not is_last:
				sequence.append(BreakCommand(time=pause))

			# Final-token pause is intentionally independent of placement.
			# In before-token placement, this gives the completed speech sequence
			# the same trailing settling pause while we do not yet merge adjacent
			# NVDA speech sequences for one control.
			if is_last and pause_after_final and pause > 0:
				sequence.append(BreakCommand(time=pause))

		return sequence

	def _get_token_prosody_commands(self, token, speech_origin="focus"):
		# A recognized navigator-object command is the only route that uses the
		# Review profile. It owns every semantic token in that one object
		# announcement, including position and hotkey.
		if speech_origin == "objectNavigation":
			return review_object_navigation_prosody_commands()
		# Focus and navigation applies to the core semantic description of a
		# focused object. It remains sequence-only: no driver settings are
		# written, and each token's commands reset before the next item.
		if getattr(token, "kind", None) in {TOKEN_NAME, TOKEN_ROLE, TOKEN_VALUE, TOKEN_STATE}:
			return focus_navigation_prosody_commands()
		# Full profile ownership is selected around the completed formatter sequence.
		# Never inject a prosody-only token path here; it would bypass Variant/Voice.
		return (), ()

	def _get_pause_for_token(self, token, profile, pauses):
		meta = getattr(token, "meta", None) or {}

		if "pause" in meta:
			try:
				return max(0, int(meta["pause"]))
			except (TypeError, ValueError):
				pass

		try:
			global_pause = max(0, int(profile.get("globalPause", 80)))
		except (TypeError, ValueError):
			global_pause = 80

		try:
			pause_value = int(pauses.get(token.kind, -1))
		except (TypeError, ValueError):
			pause_value = -1

		if pause_value < 0:
			return global_pause
		return max(0, pause_value)
