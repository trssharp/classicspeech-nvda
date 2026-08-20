# history.py
"""ClassicSpeech speech history buffer.

Stores the final speakable text that ClassicSpeech sends to NVDA after
verbosity/profile/token formatting has been applied. Speech commands such as
BreakCommand, CancellableSpeech, and CharacterModeCommand are intentionally
ignored when creating the display/copy text.
"""
from .localization import _


from collections import deque

import api
import logHandler
import speech
import ui

log = logHandler.log

DEFAULT_MAX_HISTORY_ENTRIES = 50

_HISTORY_NATIVE_PASSTHROUGH_COUNT = 0


def mark_history_native_passthrough():
    """Mark the next history-generated speech call as native passthrough.

    History entries are already final, flattened user-facing text. Sending
    them back through ClassicSpeech token classification can cause strings
    such as "Recycle Bin 1 of 17" to be interpreted as position-only speech
    and disappear.
    """
    global _HISTORY_NATIVE_PASSTHROUGH_COUNT
    _HISTORY_NATIVE_PASSTHROUGH_COUNT += 1


def consume_history_native_passthrough():
    global _HISTORY_NATIVE_PASSTHROUGH_COUNT
    if _HISTORY_NATIVE_PASSTHROUGH_COUNT <= 0:
        return False
    _HISTORY_NATIVE_PASSTHROUGH_COUNT -= 1
    return True


def sequence_to_text(sequence):
    """Return plain speakable text from an NVDA speech sequence."""
    parts = []
    for item in sequence or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


class SpeechHistoryBuffer:
    def __init__(self, maxlen=DEFAULT_MAX_HISTORY_ENTRIES):
        self._history = deque(maxlen=maxlen)
        self._pos = 0
        self._suppress_next_append = False

    def __len__(self):
        return len(self._history)

    def suppress_next_append(self):
        self._suppress_next_append = True

    def append_sequence(self, sequence):
        if self._suppress_next_append:
            self._suppress_next_append = False
            return

        text = sequence_to_text(sequence)
        if not text:
            return

        # Avoid immediate duplicates caused by filter re-entry or repeated UI
        # notifications. Real repeated announcements can still be reached once.
        if self._history and self._history[0] == text:
            self._pos = 0
            return

        self._history.appendleft(text)
        self._pos = 0

    def items(self):
        return list(self._history)

    def current(self):
        if not self._history:
            return ""
        self._pos = max(0, min(self._pos, len(self._history) - 1))
        return self._history[self._pos]

    def select(self, index):
        if not self._history:
            self._pos = 0
            return ""
        self._pos = max(0, min(index, len(self._history) - 1))
        return self._history[self._pos]

    def previous(self):
        if not self._history:
            return None
        if self._pos >= len(self._history) - 1:
            return None
        self._pos += 1
        return self._history[self._pos]

    def next(self):
        if not self._history:
            return None
        if self._pos <= 0:
            return None
        self._pos -= 1
        return self._history[self._pos]

    def bottom(self):
        """Move to the oldest/least recent history item."""
        if not self._history:
            return None
        self._pos = len(self._history) - 1
        return self._history[self._pos]

    def top(self):
        """Move to the newest/most recent history item."""
        if not self._history:
            return None
        self._pos = 0
        return self._history[self._pos]

    def clear(self):
        self._history.clear()
        self._pos = 0

    def speak_text(self, text):
        if not text:
            return
        self.suppress_next_append()
        mark_history_native_passthrough()
        speech.speak([text])

    def speak_previous(self):
        text = self.previous()
        if text is None:
            ui.message(_("Bottom of speech history"))
            return
        self.speak_text(text)

    def speak_next(self):
        text = self.next()
        if text is None:
            ui.message(_("Top of speech history"))
            return
        self.speak_text(text)

    def speak_bottom(self):
        text = self.bottom()
        if text is None:
            ui.message(_("No speech history"))
            return
        self.speak_text(text)

    def speak_top(self):
        text = self.top()
        if text is None:
            ui.message(_("No speech history"))
            return
        self.speak_text(text)

    def copy_current(self):
        return self.copy_index(self._pos)

    def copy_index(self, index):
        text = self.select(index)
        if not text:
            ui.message(_("No speech history"))
            return False
        if api.copyToClip(text):
            self.suppress_next_append()
            mark_history_native_passthrough()
            speech.speak([text, _("copied")])
            return True
        ui.message(_("Copy failed"))
        return False
