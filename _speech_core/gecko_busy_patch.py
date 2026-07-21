"""Fail-closed runtime patch for one Firefox initial Busy focus presentation.

This is intentionally limited to the ClassicSpeech opt-in experiment.  It does
not alter object state, caches, or NVDA files: it scopes a one-shot formatter
presentation copy to a strict Gecko document ``reportFocus`` call.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import inspect
from typing import Callable


class GeckoBusyPresentationPatch:
	"""Temporarily hide Busy from one strict Gecko Browse Mode focus presentation."""

	_MARKER = "_classicSpeechGeckoBusyPresentationPatch"

	def __init__(self, enabled: Callable[[], bool] | None = None):
		self._enabled = enabled or (lambda: False)
		self._pending_object: ContextVar[object | None] = ContextVar(
			"classicSpeechGeckoBusyPresentationObject", default=None,
		)
		self._document_class = None
		self._speech_module = None
		self._original_report_focus = None
		self._original_formatter = None
		self.report_focus_wrapper = None
		self.formatter_wrapper = None

	def install(self) -> bool:
		"""Patch the two exact NVDA seams when enabled and signature-compatible."""
		if self.is_installed:
			return True
		try:
			if not bool(self._enabled()):
				return False
			document_class, speech_module = self._get_targets()
			original_report_focus = getattr(document_class, "reportFocus", None)
			original_formatter = getattr(speech_module, "getPropertiesSpeech", None)
			if not self._is_compatible_report_focus(original_report_focus):
				return False
			if not self._is_compatible_formatter(original_formatter):
				return False
			if not self._prepare_reload(document_class, "reportFocus", original_report_focus):
				return False
			if not self._prepare_reload(speech_module, "getPropertiesSpeech", original_formatter):
				return False
			# Reload preparation may have restored our prior wrapper.
			original_report_focus = document_class.reportFocus
			original_formatter = speech_module.getPropertiesSpeech
			if not self._is_compatible_report_focus(original_report_focus):
				return False
			if not self._is_compatible_formatter(original_formatter):
				return False

			@wraps(original_report_focus)
			def report_focus_wrapper(obj, *args, **kwargs):
				if not self._matches(obj):
					return original_report_focus(obj, *args, **kwargs)
				token = self._pending_object.set(obj)
				try:
					return original_report_focus(obj, *args, **kwargs)
				finally:
					self._pending_object.reset(token)

			@wraps(original_formatter)
			def formatter_wrapper(*args, **kwargs):
				if self._pending_object.get() is None:
					return original_formatter(*args, **kwargs)
				states = kwargs.get("states")
				if not self._has_busy_state(states):
					return original_formatter(*args, **kwargs)
				# Consume before delegation. Recursive/nested formatter calls remain native.
				self._pending_object.set(None)
				presentation_states = set(states)
				presentation_states.discard(self._busy_state())
				presentation_kwargs = dict(kwargs)
				presentation_kwargs["states"] = presentation_states
				return original_formatter(*args, **presentation_kwargs)

			setattr(report_focus_wrapper, self._MARKER, (self, original_report_focus))
			setattr(formatter_wrapper, self._MARKER, (self, original_formatter))
			document_class.reportFocus = report_focus_wrapper
			try:
				speech_module.getPropertiesSpeech = formatter_wrapper
			except Exception:
				if document_class.reportFocus is report_focus_wrapper:
					document_class.reportFocus = original_report_focus
				return False
			self._document_class = document_class
			self._speech_module = speech_module
			self._original_report_focus = original_report_focus
			self._original_formatter = original_formatter
			self.report_focus_wrapper = report_focus_wrapper
			self.formatter_wrapper = formatter_wrapper
			return True
		except Exception:
			self.restore()
			return False

	def restore(self) -> None:
		"""Restore only methods still owned by this patch instance."""
		try:
			if (
				self._document_class is not None
				and self.report_focus_wrapper is not None
				and getattr(self._document_class, "reportFocus", None) is self.report_focus_wrapper
			):
				self._document_class.reportFocus = self._original_report_focus
		except Exception:
			pass
		try:
			if (
				self._speech_module is not None
				and self.formatter_wrapper is not None
				and getattr(self._speech_module, "getPropertiesSpeech", None) is self.formatter_wrapper
			):
				self._speech_module.getPropertiesSpeech = self._original_formatter
		except Exception:
			pass
		finally:
			self._document_class = None
			self._speech_module = None
			self._original_report_focus = None
			self._original_formatter = None
			self.report_focus_wrapper = None
			self.formatter_wrapper = None

	@property
	def is_installed(self) -> bool:
		return (
			self._document_class is not None
			and self._speech_module is not None
			and getattr(self._document_class, "reportFocus", None) is self.report_focus_wrapper
			and getattr(self._speech_module, "getPropertiesSpeech", None) is self.formatter_wrapper
		)

	def _get_targets(self):
		from NVDAObjects.IAccessible import mozilla
		import speech.speech as speech_module
		return mozilla.Document, speech_module

	def _busy_state(self):
		import controlTypes
		return controlTypes.State.BUSY

	def _has_busy_state(self, states) -> bool:
		try:
			return states is not None and self._busy_state() in states
		except Exception:
			return False

	def _matches(self, obj) -> bool:
		"""Return true only for the focused Gecko root loading in Browse Mode."""
		try:
			if not bool(self._enabled()) or not self._has_busy_state(obj.states):
				return False
			import api
			import virtualBuffers.gecko_ia2 as gecko_ia2
			ti = obj.treeInterceptor
			return (
				isinstance(ti, gecko_ia2.Gecko_ia2)
				and ti.rootNVDAObject is obj
				and api.getFocusObject() is obj
				and ti.passThrough is False
				and ti.isLoading is True
				and ti.isReady is False
			)
		except Exception:
			return False

	@staticmethod
	def _is_compatible_report_focus(method) -> bool:
		if not callable(method):
			return False
		try:
			inspect.signature(method).bind(object())
			return True
		except (TypeError, ValueError):
			return False

	@staticmethod
	def _is_compatible_formatter(method) -> bool:
		if not callable(method):
			return False
		try:
			signature = inspect.signature(method)
			reason = signature.parameters.get("reason")
			return (
				reason is not None
				and reason.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
				and any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
			)
		except (TypeError, ValueError):
			return False

	def _prepare_reload(self, owner, attribute: str, current) -> bool:
		"""Replace a prior instance only when its wrapper still owns the target."""
		marker = getattr(current, self._MARKER, None)
		if marker is None:
			return True
		try:
			previous_patch, previous_original = marker
		except (TypeError, ValueError):
			return False
		if not callable(getattr(previous_patch, "restore", None)):
			return False
		# A prior target preparation can already have restored this same patch's
		# other wrapper. That stale local reference is safe; an active foreign
		# replacement is never written over.
		if getattr(owner, attribute, None) is not current:
			return previous_patch.report_focus_wrapper is None and previous_patch.formatter_wrapper is None
		setattr(owner, attribute, previous_original)
		previous_patch.restore()
		return True
