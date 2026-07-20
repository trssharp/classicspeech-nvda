# interrupt_control.py

import functools
import sys
import time

import config
import core
import logHandler
import speech
import speech.manager

try:
	from speech.priorities import Spri
except Exception:
	try:
		from speech import Spri
	except Exception:
		Spri = None

try:
	from speech.commands import BreakCommand
except Exception:
	BreakCommand = None

log = logHandler.log


def _get_classic_speech_section():
	try:
		return config.conf["classicSpeech"]
	except Exception:
		return {}


def prevent_speech_interrupt_enabled():
	"""Return whether ClassicSpeech should keep automatic speech from interrupting.

	This master switch controls automatic focus/foreground/API speech queuing.
	"""
	try:
		return bool(_get_classic_speech_section().get("preventAutomaticSpeechInterrupt", False))
	except Exception:
		return False



def get_fallback_speech_delay_ms():
	"""Return the fallback busy timeout used when no synth-finished signal exists."""
	try:
		value = int(_get_classic_speech_section().get("automaticSpeechInterruptFallbackMs", 1000))
	except Exception:
		value = 1000
	return max(250, min(value, 4000))


# Backwards-compatible name for older call sites in this development branch.
def prevent_automatic_speech_interrupt_enabled():
	return prevent_speech_interrupt_enabled()


class SpeechInterruptController:
	"""Small wrapper for classic speech non-interruption behavior.

	There are two different concepts here:
	* automatic speech interrupt protection: focus/foreground/API speech should not
	  barge in and replace speech already being heard;
	* keyboard interrupt: pressing keys should or should not stop speech.

	This controller implements the first concept and, when the separate
	keyboard option is disabled, can also suppress ordinary keyboard-driven
	cancellation.
	"""

	def __init__(self):
		self._originalSpeak = None
		self._originalCancelSpeech = None
		self._originalShouldCancelExpiredFocusEvents = None
		self._installed = False
		self._queuedSpeaks = []
		self._busyUntil = 0.0
		self._drainScheduled = False
		self._draining = False
		self._lastQueuedLog = 0.0

	def install(self):
		if self._installed:
			return
		try:
			self._install_speak_wrapper()
			self._install_cancel_speech_wrapper()
			self._install_focus_cancel_wrapper()
			self._installed = True
			log.debug("ClassicSpeech: installed speech interrupt controller")
		except Exception:
			log.exception("ClassicSpeech: failed to install speech interrupt controller")

	def _install_speak_wrapper(self):
		original = speech.speak
		self._originalSpeak = original
		controller = self

		@functools.wraps(original)
		def wrapped_speak(speechSequence, *args, **kwargs):
			try:
				args, kwargs = controller._adjust_priority_args(args, kwargs)
			except Exception:
				log.debug("ClassicSpeech: failed to adjust speech priority", exc_info=True)

			try:
				if controller._should_queue_incoming_speech(speechSequence, args, kwargs):
					controller._queue_speak(speechSequence, args, kwargs)
					return None
			except Exception:
				log.debug("ClassicSpeech: failed while checking automatic speech queue", exc_info=True)

			result = original(speechSequence, *args, **kwargs)
			try:
				controller._mark_busy_for_sequence(speechSequence)
			except Exception:
				log.debug("ClassicSpeech: failed updating automatic speech queue timing", exc_info=True)
			return result

		speech.speak = wrapped_speak

	def _adjust_priority_args(self, args, kwargs):
		if "priority" in kwargs:
			kwargs = dict(kwargs)
			kwargs["priority"] = self._adjust_priority(kwargs.get("priority"))
		elif len(args) >= 2:
			args = list(args)
			args[1] = self._adjust_priority(args[1])
			args = tuple(args)
		return args, kwargs

	def _install_cancel_speech_wrapper(self):
		original = speech.cancelSpeech
		self._originalCancelSpeech = original
		controller = self

		@functools.wraps(original)
		def wrapped_cancel_speech(*args, **kwargs):
			try:
				if prevent_speech_interrupt_enabled() and not controller._should_allow_automatic_cancel_speech():
					log.debug("ClassicSpeech: suppressed automatic speech cancellation")
					return None
			except Exception:
				log.debug("ClassicSpeech: failed checking cancelSpeech interrupt setting", exc_info=True)
			try:
				# A real allowed cancellation means the user/system intentionally stopped
				# the current utterance. Drop our delayed automatic queue too, so keyboard
				# interrupt remains stock NVDA behavior.
				controller._clear_queued_speech()
			except Exception:
				pass
			return original(*args, **kwargs)

		speech.cancelSpeech = wrapped_cancel_speech

	def _should_allow_automatic_cancel_speech(self):
		"""Return True for safety-critical cancellation paths.

		Automatic paths we suppress include foreground, focus, menu, and related
		events that call cancelSpeech without an explicit user request.
		"""
		try:
			from speech.sayAll import SayAllHandler

			if SayAllHandler.isRunning():
				return True
		except Exception:
			pass

		try:
			frame = sys._getframe(2)
		except Exception:
			return False

		depth = 0
		while frame is not None and depth < 24:
			module_name = frame.f_globals.get("__name__", "")
			func_name = frame.f_code.co_name

			if module_name == "globalCommands" and func_name in {
				"script_speechMode",
				"script_toggleSpeechViewer",
			}:
				return True

			if module_name in {
				"core",
				"synthDriverHandler",
				"winAPI.secureDesktop",
			}:
				return True

			# Internal speech cleanup paths should stay safe.
			if module_name.startswith("speech."):
				return True

			# Foreground/focus/menu event paths are the automatic interruptions this
			# feature is meant to suppress.
			if module_name.startswith("NVDAObjects") and func_name in {
				"event_foreground",
				"event_focusEntered",
				"event_mouseMove",
				"event_selection",
			}:
				return False

			frame = frame.f_back
			depth += 1
		return False

	def _install_focus_cancel_wrapper(self):
		original = speech.manager._shouldCancelExpiredFocusEvents
		self._originalShouldCancelExpiredFocusEvents = original

		@functools.wraps(original)
		def wrapped_should_cancel_expired_focus_events():
			try:
				if prevent_speech_interrupt_enabled():
					return False
			except Exception:
				log.debug("ClassicSpeech: failed checking focus interrupt setting", exc_info=True)
			return original()

		speech.manager._shouldCancelExpiredFocusEvents = wrapped_should_cancel_expired_focus_events

	def uninstall(self):
		if not self._installed:
			return
		try:
			if self._originalSpeak is not None:
				speech.speak = self._originalSpeak
		except Exception:
			log.debug("ClassicSpeech: failed to restore speech.speak", exc_info=True)
		try:
			if self._originalCancelSpeech is not None:
				speech.cancelSpeech = self._originalCancelSpeech
		except Exception:
			log.debug("ClassicSpeech: failed to restore speech.cancelSpeech", exc_info=True)
		try:
			if self._originalShouldCancelExpiredFocusEvents is not None:
				speech.manager._shouldCancelExpiredFocusEvents = self._originalShouldCancelExpiredFocusEvents
		except Exception:
			log.debug("ClassicSpeech: failed to restore focus cancellation check", exc_info=True)
		finally:
			self._clear_queued_speech()
			self._originalSpeak = None
			self._originalCancelSpeech = None
			self._originalShouldCancelExpiredFocusEvents = None
			self._installed = False

	def _adjust_priority(self, priority):
		if Spri is None:
			return priority
		if priority is None:
			return priority
		if not prevent_speech_interrupt_enabled():
			return priority
		if priority == Spri.NOW:
			log.debug("ClassicSpeech: downgrading speech priority NOW -> NEXT")
			return Spri.NEXT
		return priority

	def _should_queue_incoming_speech(self, speechSequence, args, kwargs):
		if not prevent_speech_interrupt_enabled():
			return False
		if self._draining:
			return False
		if not speechSequence:
			return False
		# Explicit NOW has already been downgraded, but do not delay pause/resume or
		# other command-only cleanup sequences.
		if not self._sequence_has_speakable_content(speechSequence):
			return False
		return time.monotonic() < self._busyUntil

	def _queue_speak(self, speechSequence, args, kwargs):
		self._queuedSpeaks.append((list(speechSequence), tuple(args), dict(kwargs)))
		now = time.monotonic()
		if now - self._lastQueuedLog > 0.5:
			log.debug("ClassicSpeech: queued automatic speech behind current utterance")
			self._lastQueuedLog = now
		self._schedule_drain()

	def _schedule_drain(self):
		if self._drainScheduled:
			return
		delay = max(25, int(max(0.0, self._busyUntil - time.monotonic()) * 1000))
		self._drainScheduled = True
		core.callLater(delay, self._drain_queued_speech)

	def _drain_queued_speech(self):
		self._drainScheduled = False
		if not self._queuedSpeaks:
			return
		if not prevent_speech_interrupt_enabled():
			self._clear_queued_speech()
			return
		if time.monotonic() < self._busyUntil:
			self._schedule_drain()
			return
		speechSequence, args, kwargs = self._queuedSpeaks.pop(0)
		try:
			self._draining = True
			self._originalSpeak(speechSequence, *args, **kwargs)
		finally:
			self._draining = False
		self._mark_busy_for_sequence(speechSequence)
		if self._queuedSpeaks:
			self._schedule_drain()

	def _clear_queued_speech(self):
		self._queuedSpeaks = []
		self._busyUntil = 0.0
		self._drainScheduled = False

	def _mark_busy_for_sequence(self, speechSequence):
		if not prevent_speech_interrupt_enabled():
			return
		if not self._sequence_has_speakable_content(speechSequence):
			return
		duration = self._estimate_sequence_seconds(speechSequence)
		self._busyUntil = max(self._busyUntil, time.monotonic() + duration)
		self._schedule_drain()

	def _sequence_has_speakable_content(self, speechSequence):
		for item in speechSequence:
			if isinstance(item, str) and item.strip():
				return True
		return False

	def _estimate_sequence_seconds(self, speechSequence):
		chars = 0
		break_ms = 0
		for item in speechSequence:
			if isinstance(item, str):
				chars += len(item.strip())
			elif BreakCommand is not None and isinstance(item, BreakCommand):
				try:
					break_ms += int(getattr(item, "time", 0) or 0)
				except Exception:
					pass
		# Until we have a reliable synth-finished callback, use a configurable
		# fallback timeout as the floor, while still allowing longer sequences and
		# explicit BreakCommand pauses to hold the queue longer.
		fallback_seconds = get_fallback_speech_delay_ms() / 1000.0
		estimated_seconds = (chars / 13.0) + (break_ms / 1000.0) + 0.20
		seconds = max(fallback_seconds, estimated_seconds)
		return max(0.25, min(seconds, 4.0))
