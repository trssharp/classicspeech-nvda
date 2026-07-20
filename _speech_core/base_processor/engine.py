# _speech_core/base_processor/engine.py
import api
import browseMode
import config
import controlTypes
import logHandler

from .debug import should_debug_log
import speech
import textInfos

from speech.commands import (
	CharacterModeCommand,
	EndUtteranceCommand,
	PitchCommand,
	SuppressUnicodeNormalizationCommand,
)

from ..base_classifier import classify_tokens
from ..cancelable import unwrap_cancelable
from ..formatter import SpeechFormatter
from ..dialog_helpers import object_is_in_dialog, focused_button_default_status, get_default_button_name
from ..menu_hints import should_bypass_root_menu_hint
from ..maps import ALL_SPOKEN_ROLES_LOWER
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
	POSITION_MODE_EACH,
	POSITION_MODE_FIRST,
	POSITION_MODE_OFF,
)
from ..token_policy import apply_token_policy
from ..tokens import (
	TOKEN_HOTKEY,
	TOKEN_NAME,
	TOKEN_POSITION,
	TOKEN_DESCRIPTION,
	TOKEN_TOOLTIP,
	TOKEN_ROLE,
	TOKEN_STATE,
	TOKEN_VALUE,
	clone_tokens,
	token,
)
from ..verbosity import VerbosityManager
from ..key_labels import apply_key_label_to_spelling_sequence
from ..processors.text import TextProcessor

from .hotkeys import HotkeyProcessor
from .position_mode import PositionModeFilter
from .query_output import QueryOutputBuilder
from .literal_review import LiteralReviewBypass
from .semantic_cleanup import SemanticCleanup
from .default_button import DefaultButtonTokenInserter
from .object_tokens import ObjectTokenBuilder
log = logHandler.log


from .context import (
	ContextAnalyzer,
	FORM_CONTROL_ROLE_KEYS,
	MENU_CONTEXT_ROLE_KEYS,
	QUERY_SAFE_STATE_NAMES,
	ROOT_MENU_NAV_MARKER_ROLES,
)
class BaseSpeechProcessor:
	def __init__(self):
		super().__init__()
		self.verbosity = VerbosityManager()
		self.formatter = SpeechFormatter(self.verbosity)
		self.hotkeys = HotkeyProcessor()
		self.context = ContextAnalyzer(self)
		self.position_filter = PositionModeFilter(self)
		self.object_tokens = ObjectTokenBuilder(self)
		self.query_output = QueryOutputBuilder(self)
		self.literal_review = LiteralReviewBypass(self)
		self.semantic_cleanup = SemanticCleanup(self)
		self.default_button = DefaultButtonTokenInserter(self)
		self.text_processor = TextProcessor()
		self._pending_hotkey = None
		self._last_raw_sequence = None
		self._bypass_next_sequence = False

	def should_process(self, speechSequence):
		focus = api.getFocusObject()
		if not focus:
			return True
		ti = getattr(focus, "treeInterceptor", None)
		if ti and isinstance(ti, browseMode.BrowseModeDocumentTreeInterceptor):
			if not getattr(ti, "passThrough", False):
				# Do not let ARIA/web menu roles in browse mode punch through the
				# processor guard. Native menus normally leave browse interception;
				# if a hybrid app exposes a real menu while a treeInterceptor is still
				# attached, only allow it when the menu object itself is not owned by
				# the browse document.
				if self._is_native_menu_context(focus):
					if should_debug_log():
						log.debug("Browse mode detected, but native menu context is active; allowing ClassicSpeech processing")
					return True
				if should_debug_log():
					log.debug("Browse mode detected; skipping ClassicSpeech processing")
				return False
		return True

	def set_profile(self, profile_name: str):
		self.verbosity.set_profile(profile_name)

	# -------------------------
	# Focus / context helpers
	# -------------------------
	def _normalize_role_key(self, value):
		return self.context._normalize_role_key(value)

	def _normalize_accessible_label_text(self, text):
		return self.context._normalize_accessible_label_text(text)

	def _should_protect_leading_control_name(self, tokens):
		return self.context._should_protect_leading_control_name(tokens)

	def _get_object_role_key(self, obj):
		return self.context._get_object_role_key(obj)

	def _get_focus_role_key(self):
		return self.context._get_focus_role_key()

	def _object_or_ancestor_has_role(self, obj, role_keys, max_depth=8):
		return self.context._object_or_ancestor_has_role(obj, role_keys, max_depth=max_depth)

	def _is_native_menu_context(self, obj, max_depth=8):
		return self.context._is_native_menu_context(obj, max_depth=max_depth)

	def _roles_compatible(self, token_role_key, focus_role_key):
		return self.context._roles_compatible(token_role_key, focus_role_key)

	def _get_focus_context(self):
		return self.context._get_focus_context()
	def _count_instances(self, *args, **kwargs):
		return self.literal_review._count_instances(*args, **kwargs)
	def _string_tokens(self, *args, **kwargs):
		return self.literal_review._string_tokens(*args, **kwargs)
	def _meaningful_string_tokens(self, *args, **kwargs):
		return self.literal_review._meaningful_string_tokens(*args, **kwargs)
	def _looks_like_single_key(self, *args, **kwargs):
		return self.literal_review._looks_like_single_key(*args, **kwargs)
	def _looks_like_modifier_prefix(self, *args, **kwargs):
		return self.literal_review._looks_like_modifier_prefix(*args, **kwargs)
	def _looks_like_menuish_marker(self, *args, **kwargs):
		return self.literal_review._looks_like_menuish_marker(*args, **kwargs)
	def _is_compact_ui_accelerator_sequence(self, *args, **kwargs):
		return self.literal_review._is_compact_ui_accelerator_sequence(*args, **kwargs)
	def _is_spelling_sequence(self, *args, **kwargs):
		return self.literal_review._is_spelling_sequence(*args, **kwargs)
	def _sequence_has_edit_document_object_marker(self, *args, **kwargs):
		return self.literal_review._sequence_has_edit_document_object_marker(*args, **kwargs)
	def _has_say_all_or_review_callback(self, *args, **kwargs):
		return self.literal_review._has_say_all_or_review_callback(*args, **kwargs)
	def _is_likely_literal_text_review(self, *args, **kwargs):
		return self.literal_review._is_likely_literal_text_review(*args, **kwargs)
	def should_bypass_literal_review(self, *args, **kwargs):
		return self.literal_review.should_bypass_literal_review(*args, **kwargs)
	def _promote_root_menu_role_to_nav_marker(self, *args, **kwargs):
		return self.semantic_cleanup._promote_root_menu_role_to_nav_marker(*args, **kwargs)
	def _ensure_menu_context_not_silent(self, *args, **kwargs):
		return self.semantic_cleanup._ensure_menu_context_not_silent(*args, **kwargs)
	def _demote_role_token(self, *args, **kwargs):
		return self.semantic_cleanup._demote_role_token(*args, **kwargs)
	def _validate_roles(self, *args, **kwargs):
		return self.semantic_cleanup._validate_roles(*args, **kwargs)
	def _restore_native_item_state_order(self, *args, **kwargs):
		return self.semantic_cleanup._restore_native_item_state_order(*args, **kwargs)
	def _suppress_combo_expansion_states(self, *args, **kwargs):
		return self.semantic_cleanup._suppress_combo_expansion_states(*args, **kwargs)
	def _ensure_list_item_state_change_has_value(self, *args, **kwargs):
		return self.semantic_cleanup._ensure_list_item_state_change_has_value(*args, **kwargs)
	def _normalize_item_name_token_to_value(self, *args, **kwargs):
		return self.semantic_cleanup._normalize_item_name_token_to_value(*args, **kwargs)
	def _get_position_mode(self):
		return self.position_filter._get_position_mode()
	def _safe_obj_attr(self, *args, **kwargs):
		return self.object_tokens._safe_obj_attr(*args, **kwargs)
	def _safe_obj_str_attr(self, *args, **kwargs):
		return self.object_tokens._safe_obj_str_attr(*args, **kwargs)
	def _safe_selected_text(self, *args, **kwargs):
		return self.object_tokens._safe_selected_text(*args, **kwargs)
	def _safe_role_text(self, *args, **kwargs):
		return self.object_tokens._safe_role_text(*args, **kwargs)
	def _safe_state_tokens(self, *args, **kwargs):
		return self.object_tokens._safe_state_tokens(*args, **kwargs)
	def _safe_position_text(self, *args, **kwargs):
		return self.object_tokens._safe_position_text(*args, **kwargs)
	def _safe_hotkey_text(self, *args, **kwargs):
		return self.object_tokens._safe_hotkey_text(*args, **kwargs)
	def _safe_description_text(self, *args, **kwargs):
		return self.object_tokens._safe_description_text(*args, **kwargs)
	def _safe_tooltip_text(self, *args, **kwargs):
		return self.object_tokens._safe_tooltip_text(*args, **kwargs)
	def _safe_value_text(self, *args, **kwargs):
		return self.object_tokens._safe_value_text(*args, **kwargs)
	def _build_query_tokens_for_object(self, *args, **kwargs):
		return self.object_tokens._build_query_tokens_for_object(*args, **kwargs)
	def _reset_query_memory(self, *args, **kwargs):
		return self.query_output._reset_query_memory(*args, **kwargs)
	def _token_text_key(self, *args, **kwargs):
		return self.query_output._token_text_key(*args, **kwargs)
	def _append_unique_tokens(self, *args, **kwargs):
		return self.query_output._append_unique_tokens(*args, **kwargs)
	def _semantic_tokens_contain_focus_name(self, *args, **kwargs):
		return self.query_output._semantic_tokens_contain_focus_name(*args, **kwargs)
	def _semantic_tokens_look_like_context(self, *args, **kwargs):
		return self.query_output._semantic_tokens_look_like_context(*args, **kwargs)
	def _remember_query_semantic_tokens(self, *args, **kwargs):
		return self.query_output._remember_query_semantic_tokens(*args, **kwargs)
	def _get_query_memory_tokens_for_object(self, *args, **kwargs):
		return self.query_output._get_query_memory_tokens_for_object(*args, **kwargs)
	def _query_has_kind(self, *args, **kwargs):
		return self.query_output._query_has_kind(*args, **kwargs)
	def _query_has_text(self, *args, **kwargs):
		return self.query_output._query_has_text(*args, **kwargs)
	def _augment_semantic_tokens_from_focus_object(self, *args, **kwargs):
		return self.query_output._augment_semantic_tokens_from_focus_object(*args, **kwargs)
	def _build_query_tokens_from_beginner_slots(self, *args, **kwargs):
		return self.query_output._build_query_tokens_from_beginner_slots(*args, **kwargs)
	def _build_query_output(self, *args, **kwargs):
		return self.query_output._build_query_output(*args, **kwargs)
	def get_query_object_text(self, *args, **kwargs):
		return self.query_output.get_query_object_text(*args, **kwargs)
	def speak_query_object(self, *args, **kwargs):
		return self.query_output.speak_query_object(*args, **kwargs)
	def speak_current_hotkey(self, *args, **kwargs):
		return self.query_output.speak_current_hotkey(*args, **kwargs)
	def _object_signature(self, obj):
		return self.position_filter._object_signature(obj)
	def _get_position_container_signature(self, focus):
		return self.position_filter._get_position_container_signature(focus)
	def _apply_position_mode(self, semantic_tokens, mode_override=None):
		return self.position_filter._apply_position_mode(semantic_tokens, mode_override=mode_override)
	def _get_hotkey_mode(self):
		return self.hotkeys._get_hotkey_mode()

	def _hotkey_allowed_in_context(self, context, mode_override=None):
		return self.hotkeys._hotkey_allowed_in_context(context, mode_override=mode_override)

	def _apply_hotkey_mode(self, semantic_tokens, context, mode_override=None):
		return self.hotkeys._apply_hotkey_mode(semantic_tokens, context, mode_override=mode_override)

	def _strip_hotkey_commands(self, commands, semantic_tokens, removed_hotkey=False):
		return self.hotkeys._strip_hotkey_commands(commands, semantic_tokens, removed_hotkey=removed_hotkey)

	def _get_hotkey_types(self):
		return self.hotkeys._get_hotkey_types()

	def _is_access_key_hotkey(self, hotkey_text):
		return self.hotkeys._is_access_key_hotkey(hotkey_text)

	def _hotkey_type_allowed(self, hotkey_text):
		return self.hotkeys._hotkey_type_allowed(hotkey_text)

	def _apply_hotkey_type_filter(self, semantic_tokens):
		return self.hotkeys._apply_hotkey_type_filter(semantic_tokens)

	def _get_hotkey_format(self):
		return self.hotkeys._get_hotkey_format()

	def _get_dialog_access_key_only(self):
		return self.hotkeys._get_dialog_access_key_only()

	def _split_hotkey_parts(self, hotkey_text):
		return self.hotkeys._split_hotkey_parts(hotkey_text)

	def _format_hotkey_key_name(self, key):
		return self.hotkeys._format_hotkey_key_name(key)

	def _format_hotkey_modifier(self, modifier, format_value):
		return self.hotkeys._format_hotkey_modifier(modifier, format_value)

	def _format_hotkey_text(self, hotkey_text, context):
		return self.hotkeys._format_hotkey_text(hotkey_text, context)

	def _apply_hotkey_formatting(self, semantic_tokens, context):
		return self.hotkeys._apply_hotkey_formatting(semantic_tokens, context)

	def _interleave_commands_preserving_text_order(self, source_tokens, commands, built):
		"""Return formatted speech without moving surviving commands across text.

		The formatter owns semantic text ordering and may add breaks, but NVDA
		commands carry stream-position meaning. In particular, a terminal
		``IndexCommand`` following preview text must remain after that text rather
		than being prepended ahead of the formatter output.
		"""
		remaining_command_ids = {id(command) for command in commands}
		commands_by_text_boundary = {}
		text_count = 0
		for item in source_tokens:
			if isinstance(item, str):
				text_count += 1
			elif id(item) in remaining_command_ids:
				commands_by_text_boundary.setdefault(text_count, []).append(item)

		output_text_count = sum(isinstance(item, str) for item in built)
		slots = [[] for _ in range(output_text_count + 1)]
		for boundary, boundary_commands in commands_by_text_boundary.items():
			slots[min(boundary, output_text_count)].extend(boundary_commands)

		output = list(slots[0])
		seen_text = 0
		for item in built:
			output.append(item)
			if isinstance(item, str):
				seen_text += 1
				output.extend(slots[seen_text])
		return output

	def _role_order_index_for_default_token(self, *args, **kwargs):
		return self.default_button._role_order_index_for_default_token(*args, **kwargs)
	def _insert_focused_default_button_token(self, *args, **kwargs):
		return self.default_button._insert_focused_default_button_token(*args, **kwargs)
	def process(self, speechSequence, speech_origin="focus"):
		if self._bypass_next_sequence:
			self._bypass_next_sequence = False
			return speechSequence

		# Literal review/caret speech is user-facing text, not semantic focus
		# speech. It must bypass all ClassicSpeech processing unchanged.
		if self.should_bypass_literal_review(speechSequence):
			self._pending_hotkey = None
			processed = self.text_processor.process_literal_sequence(speechSequence)
			if processed != list(speechSequence):
				speechSequence.clear()
				speechSequence.extend(processed)
			if should_debug_log():
				log.debug("Literal text review detected; bypassing ClassicSpeech processing")
			return speechSequence

		# Narrow full passthrough for root popup menus that already speak cleanly
		# in native NVDA speech, such as "NVDA menu" and "Context menu".
		# MenuHintHelper uses the same table to suppress the generic open hint.
		try:
			if should_bypass_root_menu_hint(api.getFocusObject()):
				if should_debug_log():
					log.debug("Root menu passthrough detected; bypassing ClassicSpeech processing")
				return speechSequence
		except Exception:
			pass

		if not self.should_process(speechSequence):
			return speechSequence

		if should_debug_log():
			log.debug(f"HOOK INPUT: {speechSequence}")

		tokens = list(unwrap_cancelable(speechSequence))
		if not tokens:
			return speechSequence

		context = self._get_focus_context()

		if self._is_spelling_sequence(tokens, context):
			key_label_sequence = apply_key_label_to_spelling_sequence(tokens)
			if key_label_sequence is not None:
				if should_debug_log():
					log.debug(
						"Spelling sequence detected; applying key-label override"
					)
				return key_label_sequence
			if should_debug_log():
				log.debug(
					"Spelling sequence detected; skipping ClassicSpeech processing"
				)
			return speechSequence

		commands = [t for t in tokens if not isinstance(t, str)]
		text_tokens = [t for t in tokens if isinstance(t, str)]
		if not text_tokens:
			return speechSequence

		if self._is_likely_literal_text_review(tokens, context):
			self._pending_hotkey = None
			if should_debug_log():
				log.debug("Literal text review detected; bypassing semantic classification")
			return speechSequence

		semantic_tokens = classify_tokens(
			tokens,
			context=context,
			protect_first_name=self._should_protect_leading_control_name(tokens),
		)
		# 27e: restore classic pre-normalization behavior. Item-name-to-value
		# promotion was too aggressive and caused list roles to disappear in
		# plain item sequences such as ['General', '1 of 27']. Keep merging
		# structural only for now; revisit itemText/value as a separate pass.
		semantic_tokens = self._promote_root_menu_role_to_nav_marker(semantic_tokens)
		# Normal speech must only reshape tokens NVDA actually supplied.
		# Do not fetch api.getFocusObject().description here; some UIA
		# controls expose window titles/paths as descriptions, which can
		# get appended to unrelated console output or clock announcements.
		# NVDA+Tab query still fetches description intentionally.
		self._remember_query_semantic_tokens(semantic_tokens, context)
		self._last_raw_sequence = list(tokens)
		semantic_tokens = self._validate_roles(semantic_tokens)
		semantic_tokens = self._suppress_combo_expansion_states(semantic_tokens)
		semantic_tokens = self._apply_position_mode(semantic_tokens)
		semantic_tokens, removed_hotkey = self._apply_hotkey_mode(semantic_tokens, context)
		had_hotkey_before_type_filter = any(
			getattr(tok, "kind", None) == TOKEN_HOTKEY for tok in semantic_tokens
		)
		semantic_tokens = self._apply_hotkey_type_filter(semantic_tokens)
		removed_by_type_filter = had_hotkey_before_type_filter and not any(
			getattr(tok, "kind", None) == TOKEN_HOTKEY for tok in semantic_tokens
		)
		semantic_tokens = self._apply_hotkey_formatting(semantic_tokens, context)

		commands = self._strip_hotkey_commands(
			commands,
			semantic_tokens,
			removed_hotkey=removed_hotkey or removed_by_type_filter,
		)

		focus = api.getFocusObject()
		focus_role_key = self._get_focus_role_key()
		selected_text = ""
		if focus_role_key in {"editabletext", "editcombo", "document"}:
			selected_text = self._safe_selected_text(focus)

		semantic_tokens, self._pending_hotkey = apply_token_policy(
			semantic_tokens,
			context=context,
			focus_role_key=focus_role_key,
			pending_hotkey=self._pending_hotkey,
			suppress_editable_text_value=True,
			selected_text=selected_text,
		)

		semantic_tokens = self._insert_focused_default_button_token(semantic_tokens, focus)
		semantic_tokens = self._ensure_list_item_state_change_has_value(semantic_tokens)
		semantic_tokens = self._restore_native_item_state_order(semantic_tokens)

		built = self.formatter.format(
			semantic_tokens,
			profile_config=self.verbosity.get_profile_config(),
			speech_origin=speech_origin,
		)
		built = self._ensure_menu_context_not_silent(built, semantic_tokens, context)

		output = self._interleave_commands_preserving_text_order(tokens, commands, built)
		speechSequence.clear()
		speechSequence.extend(output)

		if should_debug_log():
			log.debug(f"HOOK OUTPUT: {speechSequence}")

		return speechSequence
