"""Persistent, same-synth audition owned only by the Voice Profiles dialog.

Unlike an automatic category transaction or indexed Preview, ordinary speech
cancellation does not end this session. No driver is loaded, patched or muted.
NVDA saves driver settings into an unnamed overlay; pre-save removes it before
NVDA writes named profiles. Post-save resumption is owner/generation guarded.
"""
from __future__ import annotations

import copy

from ..voice_profile_overlay import VoiceProfileOverlay
from .voice_profiles_preview import ordered_setting_ids as _ordered_ids


class VoiceProfileAuditionOverlay(VoiceProfileOverlay):
    """Dialog-only extension: never leave an unnamed profile dirty for save.

    NVDA's AggregatedSection marks the top profile name dirty on a write.
    Unnamed overlays aren't in _profileCache and cannot be serialized. Preserve
    pre-existing dirty ownership; remove only this overlay's transient marker
    after its writes have been carried back to the actual write target.
    """
    def enter(self):
        if self.active:
            return
        self._unnamed_was_dirty = None in getattr(self._config, "_dirtyProfiles", ())
        super().enter()

    def exit(self):
        was_active = self.active
        super().exit()
        dirty = getattr(self._config, "_dirtyProfiles", None)
        if was_active and dirty is not None and not self._unnamed_was_dirty:
            dirty.discard(None)


def _public_settings(driver):
    return {setting.id: setting for setting in driver.supportedSettings
            if getattr(setting, "id", "") and not setting.id.startswith("_")}


class VoiceProfileAudition:
    def __init__(self, driver, *, active_synth_getter, cancel_speech,
                 overlay_factory, pre_save, post_save, synth_changed,
                 schedule, on_error, config_manager):
        self.driver = driver
        self._get_synth = active_synth_getter
        self._cancel_speech = cancel_speech
        self._overlay_factory = overlay_factory
        self._schedule = schedule
        self._on_error = on_error
        self._overlay = None
        self._requested = None
        self._generation = 0
        self._closed = False
        self._restoring = False
        self._busy = False
        self._restore_pending = False
        # Drain any pre-existing category transaction BEFORE capturing native
        # values. Refuse a driver mismatch, rather than loading another synth.
        cancel_speech()
        if active_synth_getter() is not driver:
            raise RuntimeError("The active synthesizer changed; reopen Voice Profiles")
        self._settings = _public_settings(driver)
        # An incomplete capture cannot authorize any live mutation.
        self._original = {key: copy.deepcopy(getattr(driver, key)) for key in self._settings}
        self._actions = ((pre_save, self._before_save), (post_save, self._after_save),
                         (synth_changed, self._synth_changed))
        self._config = config_manager
        self._original_save = config_manager.save
        self._had_own_save = "save" in vars(config_manager)
        self._own_save = vars(config_manager).get("save")
        self._save_wrapper = self._save_isolated
        registered = []
        try:
            for action, handler in self._actions:
                action.register(handler)
                registered.append((action, handler))
            config_manager.save = self._save_wrapper
        except Exception:
            for action, handler in registered:
                action.unregister(handler)
            raise

    @property
    def active(self):
        return self._overlay is not None and self._overlay.active

    @property
    def generation(self):
        return self._generation

    def snapshot(self):
        """Public, actual post-selector values for the editor's current view."""
        return {key: copy.deepcopy(getattr(self.driver, key)) for key in _public_settings(self.driver)}

    def select(self, snapshot):
        if self._closed or self._get_synth() is not self.driver:
            raise RuntimeError("The audition owner or synthesizer is no longer active")
        if self._busy or self._restoring:
            raise RuntimeError("A Voice Profile audition transition is already running")
        self._generation += 1
        self._requested = copy.deepcopy(snapshot) if snapshot else None
        self.pause()
        if self._restore_pending:
            raise RuntimeError("Native synthesizer restoration is incomplete")
        if self._requested is not None:
            self._apply()

    def _apply(self):
        if self._closed or self._get_synth() is not self.driver:
            return
        self._busy = True
        try:
            self._overlay = self._overlay_factory(self._original)
            self._overlay.enter()
            # Re-discover advertised settings after selectors: dependent choices
            # and supported controls can change when a voice is selected.
            remaining = dict(self._requested)
            while remaining:
                settings = _public_settings(self.driver)
                ids = _ordered_ids(settings, remaining)
                if not ids:
                    break
                key = ids[0]
                value = remaining.pop(key)
                setting = settings[key]
                if hasattr(setting, "minVal") and (
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not setting.minVal <= value <= setting.maxVal
                ):
                    raise ValueError(f"Invalid audition numeric setting: {key}")
                setattr(self.driver, key, value)
                if self._closed or self._get_synth() is not self.driver:
                    raise RuntimeError("Synthesizer changed during audition")
            self._overlay.synchronize_from_driver(self.driver)
        except Exception:
            self.pause()
            raise
        finally:
            self._busy = False

    def pause(self):
        """Restore native values and remove the overlay, retaining selection."""
        if self._restoring or (self._overlay is None and not self._restore_pending):
            return
        self._restoring = True
        try:
            # Clear SpeechManager's queued/active transactions before restoring.
            # Preview's synchronous cancellation restores into this audition
            # first, never after a later selected profile has taken ownership.
            try:
                self._cancel_speech()
            except Exception:
                self._report("cancelSpeech")
            self._restore_pending = False
            for key in _ordered_ids(self._settings, self._original):
                try:
                    setattr(self.driver, key, copy.deepcopy(self._original[key]))
                except Exception:
                    self._restore_pending = True
                    self._report(key)
            if self._overlay is not None:
                self._overlay.exit()
            self._overlay = None
        finally:
            self._restoring = False

    def _save_isolated(self, *args, **kwargs):
        # A second save may run before post-save CallAfter resumes audition.
        # Shield only the early driver callbacks, never later pre-save writers
        # or serialization. The native save body and handler order are unchanged.
        if not self._closed and self._requested is not None and self._overlay is None:
            self._overlay = self._overlay_factory(self._original)
            self._overlay.enter()
        try:
            return self._original_save(*args, **kwargs)
        finally:
            # Also remove the temporary shield if native save failed before our
            # pre-save handler (or returned without post_configSave).
            self.pause()

    def _before_save(self, **kwargs):
        self._generation += 1
        self.pause()

    def _after_save(self, **kwargs):
        generation = self._generation
        def resume():
            if (self._closed or generation != self._generation
                    or self._requested is None):
                return
            try:
                self.select(self._requested)
            except Exception:
                self._report("resume")
        self._schedule(resume)

    def _synth_changed(self, **kwargs):
        self.close()

    def close(self):
        """Invalidate first; restore and unsubscribe exactly once."""
        if self._closed:
            self.pause()  # Retry only incomplete restoration, never replay success.
            return
        self._closed = True
        self._generation += 1
        self._requested = None
        try:
            self.pause()
        finally:
            # Restore only our own instance wrapper; never overwrite a later owner.
            if self._config.save is self._save_wrapper:
                if self._had_own_save:
                    self._config.save = self._own_save
                else:
                    del self._config.save
            for action, handler in self._actions:
                try:
                    action.unregister(handler)
                except Exception:
                    self._report("unregister")

    def _report(self, key):
        try:
            self._on_error(key)
        except Exception:
            pass
