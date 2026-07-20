"""Restoration-safe, same-synth Voice Profile preview lifecycle.

``VoiceProfilePreviewController`` deliberately has no wx or NVDA imports.  The
NVDA dialog supplies the speech/events/scheduler adapters, while this module is
unit-testable with fake drivers and event actions.  A preview owns exactly one
captured active synthesizer and restores that driver's complete advertised
settings only after its own indexed utterance has completed or been canceled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_PREVIEW_TEXT = "This is a preview of the selected ClassicSpeech voice profile."


def supported_setting_ids(driver) -> tuple[str, ...]:
	"""Return every public, named setting advertised by ``driver`` in order."""
	return tuple(
		setting_id
		for setting in getattr(driver, "supportedSettings", ())
		if (setting_id := getattr(setting, "id", "")) and not setting_id.startswith("_")
	)


def preview_timeout_seconds(text: str) -> int:
	"""Give a short preview 15 seconds, with bounded extra time for long text."""
	return min(30, 15 + min(15, len(text or "") // 20))


def _stop_scheduled(handle) -> None:
	if handle is None:
		return
	for method_name in ("Stop", "stop", "cancel"):
		method = getattr(handle, method_name, None)
		if method is not None:
			try:
				method()
			except Exception:
				pass
			return


@dataclass(frozen=True)
class PreviewEvents:
	"""The four NVDA actions the controller subscribes to for one preview."""
	synth_index_reached: Any
	synth_done_speaking: Any
	synth_changed: Any
	speech_canceled: Any


class VoiceProfilePreviewController:
	"""One asynchronous, restoration-safe preview transaction.

	All dependencies are injected so the controller can be exercised outside
	NVDA. Actions need only provide ``register`` and ``unregister``. The
	scheduler takes ``(seconds, callback)`` and returns a stoppable handle.
	"""

	def __init__(
		self,
		snapshot: dict,
		text: str,
		*,
		speak: Callable[[list], None],
		index_command_factory: Callable[[int], object],
		events: PreviewEvents,
		scheduler: Callable[[int, Callable[[], None]], object],
		token_factory: Callable[[], int],
		active_synth_getter: Callable[[], object],
		on_restore_error: Callable[[str], None] | None = None,
		on_finished: Callable[[str], None] | None = None,
	):
		self.snapshot = dict(snapshot or {})
		self.text = text or DEFAULT_PREVIEW_TEXT
		self._speak = speak
		self._index_command_factory = index_command_factory
		self._events = events
		self._scheduler = scheduler
		self._token_factory = token_factory
		self._active_synth_getter = active_synth_getter
		self._on_restore_error = on_restore_error
		self._on_finished = on_finished
		self._captured_driver = None
		self._original_values: dict[str, object] = {}
		self._token: int | None = None
		self._timeout_handle = None
		self._state = "idle"
		self._subscribed = False

	@property
	def active(self) -> bool:
		return self._state in ("queued", "waitingDone")

	@property
	def state(self) -> str:
		return self._state

	@property
	def token(self) -> int | None:
		return self._token

	@property
	def captured_driver(self):
		return self._captured_driver

	def start(self) -> bool:
		"""Capture, subscribe, apply and queue the preview. Reject duplicate starts."""
		if self.active:
			return False
		self._captured_driver = self._active_synth_getter()
		if self._captured_driver is None:
			raise RuntimeError("No active synthesizer is available for preview")
		self._original_values = {
			setting_id: getattr(self._captured_driver, setting_id)
			for setting_id in supported_setting_ids(self._captured_driver)
		}
		self._token = self._token_factory()
		self._state = "queued"
		self._subscribe()
		try:
			# A voice assignment can load dependent native defaults. Apply it first,
			# then only the profile's explicit values; never replay inherited values.
			setting_ids = supported_setting_ids(self._captured_driver)
			apply_order = [
				setting_id for setting_id in ("voice", "variant")
				if setting_id in setting_ids and setting_id in self.snapshot
			]
			apply_order.extend(
				setting_id for setting_id in setting_ids
				if setting_id not in {"voice", "variant"} and setting_id in self.snapshot
			)
			for setting_id in apply_order:
				setattr(self._captured_driver, setting_id, self.snapshot[setting_id])
				# A driver setting can synchronously trigger a synth change/cancel.
				# Never continue mutating after that handler restored the snapshot.
				if not self.active:
					return True
			# The terminal index makes completion attributable to this exact preview.
			self._speak([self.text, self._index_command_factory(self._token)])
			# Normally speak queues asynchronously, but a fake/third-party driver can
			# report cancellation or completion before speak returns.
			if self.active:
				self._timeout_handle = self._scheduler(preview_timeout_seconds(self.text), self._on_timeout)
		except Exception:
			self.finish("startError")
			raise
		return True

	def cancel(self) -> None:
		"""Cancel this preview's currently active synth, then restore exactly once."""
		if not self.active:
			return
		self._cancel_captured_active_driver()
		self.finish("canceled")

	def _subscribe(self) -> None:
		if self._subscribed:
			return
		self._events.synth_index_reached.register(self._on_synth_index_reached)
		self._events.synth_done_speaking.register(self._on_synth_done_speaking)
		self._events.synth_changed.register(self._on_synth_changed)
		self._events.speech_canceled.register(self._on_speech_canceled)
		self._subscribed = True

	def _unsubscribe(self) -> None:
		if not self._subscribed:
			return
		for action, handler in (
			(self._events.synth_index_reached, self._on_synth_index_reached),
			(self._events.synth_done_speaking, self._on_synth_done_speaking),
			(self._events.synth_changed, self._on_synth_changed),
			(self._events.speech_canceled, self._on_speech_canceled),
		):
			try:
				action.unregister(handler)
			except Exception:
				pass
		self._subscribed = False

	def _on_synth_index_reached(self, *, synth=None, index=None, **_kwargs) -> None:
		if self._state != "queued":
			return
		if synth is self._captured_driver and index == self._token:
			self._state = "waitingDone"

	def _on_synth_done_speaking(self, *, synth=None, **_kwargs) -> None:
		# Ignore completion before our own index and completion from any other synth.
		if self._state == "waitingDone" and synth is self._captured_driver:
			self.finish("completed")

	def _on_speech_canceled(self, **_kwargs) -> None:
		# This action is global and has no synth argument. Be conservative: another
		# cancellation can leave our applied values audible, so restore immediately.
		if self.active:
			self.finish("speechCanceled")

	def _on_synth_changed(self, **_kwargs) -> None:
		if self.active:
			self.finish("synthChanged")

	def _on_timeout(self) -> None:
		if not self.active:
			return
		self._cancel_captured_active_driver()
		self.finish("timedOut")

	def _cancel_captured_active_driver(self) -> None:
		if self._active_synth_getter() is not self._captured_driver:
			return
		cancel = getattr(self._captured_driver, "cancel", None)
		if cancel is not None:
			try:
				cancel()
			except Exception:
				pass

	def finish(self, reason: str) -> bool:
		"""Idempotently unsubscribe, stop timeout, restore, and release busy state."""
		if self._state in ("idle", "finished"):
			return False
		self._state = "finished"
		_stop_scheduled(self._timeout_handle)
		self._timeout_handle = None
		self._unsubscribe()
		# Restore voice first so a driver-side native reset cannot overwrite the
		# following captured dependent values.
		restore_ids = (["voice"] if "voice" in self._original_values else [])
		restore_ids.extend(setting_id for setting_id in self._original_values if setting_id != "voice")
		for setting_id in restore_ids:
			value = self._original_values[setting_id]
			try:
				setattr(self._captured_driver, setting_id, value)
			except Exception:
				if self._on_restore_error is not None:
					try:
						self._on_restore_error(setting_id)
					except Exception:
						pass
		if self._on_finished is not None:
			try:
				self._on_finished(reason)
			except Exception:
				pass
		return True


def preview_snapshot(driver, snapshot: dict, announce, on_restore_error=None) -> None:
	"""Legacy synchronous helper retained for existing non-lifecycle callers/tests."""
	setting_ids = supported_setting_ids(driver)
	original_values = {setting_id: getattr(driver, setting_id) for setting_id in setting_ids}
	try:
		setting_ids = supported_setting_ids(driver)
		apply_order = [
			setting_id for setting_id in ("voice", "variant")
			if setting_id in setting_ids and setting_id in snapshot
		]
		apply_order.extend(
			setting_id for setting_id in setting_ids
			if setting_id not in {"voice", "variant"} and setting_id in snapshot
		)
		for setting_id in apply_order:
			setattr(driver, setting_id, snapshot[setting_id])
		announce()
	finally:
		restore_ids = (["voice"] if "voice" in original_values else [])
		restore_ids.extend(setting_id for setting_id in original_values if setting_id != "voice")
		for setting_id in restore_ids:
			value = original_values[setting_id]
			try:
				setattr(driver, setting_id, value)
			except Exception:
				if on_restore_error is not None:
					try:
						on_restore_error(setting_id)
					except Exception:
						pass
