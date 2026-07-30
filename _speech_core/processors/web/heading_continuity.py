"""Opt-in continuation-line heading presentation for settled Browse Mode buffers.

This is deliberately a private-NVDA-API experiment. It does not rewrite virtual
buffer text, offsets, selection, quick-navigation nodes, or braille data. For a
ready active Browse Mode caret line or Say All reading chunk, it uses NVDA's own
stable virtual-buffer control-stack identity and suppresses only heading
presentation already known to belong to that same heading.
"""
from __future__ import annotations

import contextvars
import functools


class HeadingContinuityRuntime:
	"""Own a version-guarded, fail-closed text-info presentation wrapper."""

	_MARKER = "_classicSpeechHeadingContinuityRuntime"

	def __init__(
		self,
		is_enabled,
		get_focus_object,
		line_unit,
		caret_reason,
		reading_chunk_unit,
		sayall_reason,
		heading_role=None,
		log=None,
	):
		self._is_enabled = is_enabled
		self._get_focus_object = get_focus_object
		self._line_unit = line_unit
		self._caret_reason = caret_reason
		self._reading_chunk_unit = reading_chunk_unit
		self._sayall_reason = sayall_reason
		self._heading_role = heading_role
		self._log = log
		self._presentationScope = contextvars.ContextVar(
			"classicSpeechHeadingContinuityPresentation", default=False
		)
		self._speechModule = None
		self._speechApiModule = None
		self._sayAllHandler = None
		self._originalGetTextInfoSpeech = None
		self._originalGetControlFieldSpeech = None
		self._originalSayAllGetTextInfoSpeech = None
		self._wrappedGetTextInfoSpeech = None
		self._wrappedGetControlFieldSpeech = None

	def _debug(self, message):
		if self._log is not None:
			try:
				self._log.debug(message, exc_info=True)
			except Exception:
				pass

	def _trace(self, message):
		if self._log is not None:
			try:
				self._log.debug("ClassicSpeech heading continuity: %s", message)
			except Exception:
				pass

	def is_current_caret_line(self, info):
		"""Return true only for a caret line in the focused, ready VBuf."""
		try:
			if not self._is_enabled():
				return False
			document = getattr(info, "obj", None)
			if document is None:
				return False
			if getattr(document, "isReady", False) is not True:
				return False
			if getattr(document, "VBufHandle", None) is None:
				return False
			focus = self._get_focus_object()
			focus_tree_interceptor = getattr(focus, "treeInterceptor", None)
			# A browser's focused document can omit treeInterceptor while its caret
			# TextInfo still belongs to the active VBuf. A non-None different buffer
			# is definitive stale-buffer evidence; an omitted value is not.
			if focus_tree_interceptor is not None and focus_tree_interceptor is not document:
				self._trace("rejected stale current-caret buffer")
				return False
			return True
		except Exception:
			self._debug("ClassicSpeech: heading-continuity current-caret check failed")
		return False

	def _should_scope_presentation(self, info, unit, reason):
		is_caret_line = unit == self._line_unit and reason == self._caret_reason
		is_sayall_reading_chunk = unit == self._reading_chunk_unit and reason == self._sayall_reason
		if not (is_caret_line or is_sayall_reading_chunk):
			return False
		return self.is_current_caret_line(info)

	def install(self, speech_module, speech_api_module, sayall_handler=None):
		"""Install paired wrappers, declining incompatible or competing patches."""
		if (
			self._speechModule is speech_module
			and self._speechApiModule is speech_api_module
			and self._sayAllHandler is sayall_handler
			and self._wrappedGetTextInfoSpeech is not None
		):
			return True
		try:
			original_text = getattr(speech_module, "getTextInfoSpeech")
			# TextInfo imports the public speech package and resolves this function
			# there. Patching speech.speech alone leaves that package binding intact.
			original_control = getattr(speech_api_module, "getControlFieldSpeech")
			if not callable(original_text) or not callable(original_control):
				return False
			original_sayall_text = getattr(sayall_handler, "_getTextInfoSpeech", None)
			if original_sayall_text is not None and not callable(original_sayall_text):
				return False
			existing = getattr(speech_module, self._MARKER, None)
			if existing is not None and existing is not self:
				return False

			@functools.wraps(original_text)
			def wrapped_get_text_info_speech(*args, **kwargs):
				info = args[0] if args else kwargs.get("info")
				unit = kwargs.get("unit") if "unit" in kwargs else (args[3] if len(args) > 3 else None)
				reason = kwargs.get("reason") if "reason" in kwargs else (args[4] if len(args) > 4 else None)
				scoped = self._should_scope_presentation(info, unit, reason)
				if scoped:
					self._trace("entered caret-line or Say All presentation scope")
				token = self._presentationScope.set(scoped)
				try:
					yield from original_text(*args, **kwargs)
				finally:
					self._presentationScope.reset(token)

			@functools.wraps(original_control)
			def wrapped_get_control_field_speech(attrs, ancestors, field_type, *args, **kwargs):
				if (
					self._presentationScope.get()
					and field_type == "start_inControlFieldStack"
					and hasattr(attrs, "get")
					and attrs.get("role") == self._heading_role
				):
					# NVDA assigns this field type only after comparing current and cached
					# controls by stable uniqueID. Therefore this is the same heading.
					self._trace("suppressing continuation-line heading presentation")
					return []
				return original_control(attrs, ancestors, field_type, *args, **kwargs)

			speech_module.getTextInfoSpeech = wrapped_get_text_info_speech
			speech_api_module.getControlFieldSpeech = wrapped_get_control_field_speech
			if original_sayall_text is not None:
				# Say All captures getTextInfoSpeech during speech initialization. Its
				# handler therefore retains the pre-wrapper function unless patched too.
				sayall_handler._getTextInfoSpeech = wrapped_get_text_info_speech
			setattr(speech_module, self._MARKER, self)
			self._speechModule = speech_module
			self._speechApiModule = speech_api_module
			self._sayAllHandler = sayall_handler
			self._originalGetTextInfoSpeech = original_text
			self._originalGetControlFieldSpeech = original_control
			self._originalSayAllGetTextInfoSpeech = original_sayall_text
			self._wrappedGetTextInfoSpeech = wrapped_get_text_info_speech
			self._wrappedGetControlFieldSpeech = wrapped_get_control_field_speech
			self._trace("installed text-info, public-control-field, and Say All wrappers")
			return True
		except Exception:
			self._debug("ClassicSpeech: failed to install heading-continuity presentation")
			return False

	def restore(self):
		"""Restore only the methods this runtime still owns."""
		speech_module = self._speechModule
		if speech_module is None:
			return
		try:
			if getattr(speech_module, "getTextInfoSpeech", None) is self._wrappedGetTextInfoSpeech:
				speech_module.getTextInfoSpeech = self._originalGetTextInfoSpeech
			speech_api_module = self._speechApiModule
			if (
				speech_api_module is not None
				and getattr(speech_api_module, "getControlFieldSpeech", None) is self._wrappedGetControlFieldSpeech
			):
				speech_api_module.getControlFieldSpeech = self._originalGetControlFieldSpeech
			sayall_handler = self._sayAllHandler
			if (
				sayall_handler is not None
				and self._originalSayAllGetTextInfoSpeech is not None
				and getattr(sayall_handler, "_getTextInfoSpeech", None) is self._wrappedGetTextInfoSpeech
			):
				sayall_handler._getTextInfoSpeech = self._originalSayAllGetTextInfoSpeech
			if getattr(speech_module, self._MARKER, None) is self:
				delattr(speech_module, self._MARKER)
		except Exception:
			self._debug("ClassicSpeech: failed to restore heading-continuity presentation")
		finally:
			self._speechModule = None
			self._speechApiModule = None
			self._sayAllHandler = None
			self._originalGetTextInfoSpeech = None
			self._originalGetControlFieldSpeech = None
			self._originalSayAllGetTextInfoSpeech = None
			self._wrappedGetTextInfoSpeech = None
			self._wrappedGetControlFieldSpeech = None


def install(log=None):
	"""Create the live runtime wrapper for released NVDA, or fail closed."""
	try:
		import api
		from controlTypes import OutputReason, Role
		import textInfos
		import speech as speech_api_module
		from speech import sayAll as sayall_module
		from speech import speech as speech_module
		from ...settings.web.heading_continuity_config import get_heading_continuity_enabled

		runtime = HeadingContinuityRuntime(
			is_enabled=get_heading_continuity_enabled,
			get_focus_object=api.getFocusObject,
			line_unit=textInfos.UNIT_LINE,
			caret_reason=OutputReason.CARET,
			reading_chunk_unit=textInfos.UNIT_READINGCHUNK,
			sayall_reason=OutputReason.SAYALL,
			heading_role=Role.HEADING,
			log=log,
		)
		if runtime.install(speech_module, speech_api_module, getattr(sayall_module, "SayAllHandler", None)):
			return runtime
		runtime._trace("required private speech APIs were unavailable")
		return None
	except Exception:
		if log is not None:
			try:
				log.debug("ClassicSpeech: heading-continuity API unavailable", exc_info=True)
			except Exception:
				pass
		return None
