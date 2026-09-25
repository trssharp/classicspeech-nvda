"""Speech-only presentation for dedicated Windows toast arrival events.

Private NVDA UIA seam: never wrap ui.message or Notification.event_alert globally.
Keep the native event body (notification preference, dedupe and braille) intact.
Formatting is orthogonal to the existing System Voice/profile routing: neither
formatting nor the source scope changes that route. Remove the exact leading
English prefix and only the recognized terminal count/window scaffolding.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import re

# Exact English UIA suffix observed in live toasts; no whitespace/case folding.
# The optional Actions marker includes Windows' extra period, not body words.
_TERMINAL_COUNT = re.compile(r'(?: \. Actions\.)? [0-9]+ of [0-9]+\Z')

_toast = ContextVar('classicSpeechIncomingToast', default=None)
_EVENTS = (
    ('Toast_win8', 'event_UIA_toolTipOpened'),
    ('Toast_win10', 'event_UIA_window_windowOpen'),
    ('Toast_win10', 'event_UIA_toolTipOpened'),
)


def current_toast():
    return _toast.get()


@contextmanager
def toast_scope(obj):
    token = _toast.set(obj)
    try:
        yield
    finally:
        _toast.reset(token)


def compact_name(name):
    """Remove only the exact leading English prefix, retaining the rest verbatim."""
    prefix = 'New notification from '
    if not isinstance(name, str) or not name.startswith(prefix):
        return name
    return name[len(prefix):]


def transform(sequence):
    obj = current_toast()
    if obj is None:
        return sequence
    try:
        name = obj.name
        compact = compact_name(name)
        # Never change the source object, join command-bearing fragments, or
        # rewrite a substring. Unknown layouts keep the existing prefix policy.
        text = [(i, item) for i, item in enumerate(sequence) if isinstance(item, str)]
        indices = [i for i, item in text if item == name]
        if len(indices) != 1:
            return sequence
        name_index = indices[0]
        window_index = None
        # Only the observed two-text-item shape is authorized. Commands can
        # precede, separate, or follow the text and retain identity and order.
        if len(text) == 2 and text[0][0] == name_index and text[1][1] == 'window':
            suffix = _TERMINAL_COUNT.search(compact)
            if suffix is not None and suffix.start() > 0:
                compact = compact[:suffix.start()]
                window_index = text[1][0]
        if compact == name and window_index is None:
            return sequence
        result = list(sequence)
        result[name_index] = compact
        if window_index is not None:
            del result[window_index]
        return result
    except Exception:
        return sequence


class ToastArrivalRuntime:
    """Identity-safe, inert-after-restore wrapper ownership."""
    def __init__(self, is_active, log):
        self._is_active = is_active
        self._log = log
        self._routes = []
        self._alive = True

    def install(self):
        if self._routes or not self._alive:
            return
        try:
            import NVDAObjects.UIA as uia
        except ImportError:
            return
        for class_name, event_name in _EVENTS:
            cls = getattr(uia, class_name, None)
            # Only methods owned by these dedicated overlays, not inherited
            # generic UIA notification/tooltip methods on a different release.
            original = vars(cls).get(event_name) if isinstance(cls, type) else None
            if not callable(original):
                continue

            @wraps(original)
            def wrapped(obj, *args, __original=original, **kwargs):
                if not self._alive or not self._is_active():
                    return __original(obj, *args, **kwargs)
                with toast_scope(obj):
                    return __original(obj, *args, **kwargs)

            try:
                setattr(cls, event_name, wrapped)
                self._routes.append((cls, event_name, original, wrapped))
            except Exception:
                self._log.debug('ClassicSpeech: toast arrival seam unavailable', exc_info=True)

    def restore(self):
        self._alive = False
        for cls, name, original, wrapper in reversed(self._routes):
            if getattr(cls, name, None) is wrapper:
                setattr(cls, name, original)
        self._routes.clear()
