"""Optional formatting of NVDA's native title command, never focus speech.

Execute the native code with invocation-local api/ui facades, not shared module
patches. The foreground object is captured from the native lookup; its security
check and title fallbacks still run natively. Only the message after native repeat
count zero is formatted. Spelling/copy and all downstream voice/history hooks
remain native. This private seam is covered against actual NVDA master source.
"""
import ctypes
from ctypes import wintypes
import functools
import types

from .localization import _
from .settings.misc_config import _get_include_window_state_in_title


class _WindowPlacement(ctypes.Structure):
    _fields_ = [('length', wintypes.UINT), ('flags', wintypes.UINT),
                ('showCmd', wintypes.UINT), ('ptMinPosition', wintypes.POINT),
                ('ptMaxPosition', wintypes.POINT), ('rcNormalPosition', wintypes.RECT)]


# NVDA master winBindings.user32 does not currently export GetWindowPlacement.
# A private function pointer avoids changing ctypes.windll's shared signatures.
try:
    _get_window_placement = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_WindowPlacement)
    )(('GetWindowPlacement', ctypes.WinDLL('user32', use_last_error=True)))
except (AttributeError, OSError):
    # Non-Windows harnesses and unavailable providers retain native title speech.
    _get_window_placement = None


def get_window_state(handle):
    if _get_window_placement is None or not isinstance(handle, int) or isinstance(handle, bool) or handle <= 0:
        return None
    placement = _WindowPlacement()
    placement.length = ctypes.sizeof(placement)
    if not _get_window_placement(handle, ctypes.byref(placement)):
        return None
    return {1: 'normal', 2: 'minimized', 3: 'maximized',
            6: 'minimized', 7: 'minimized', 11: 'minimized'}.get(placement.showCmd)


class _Facade:
    def __init__(self, original, **overrides):
        self._original = original
        self.__dict__.update(overrides)

    def __getattr__(self, name):
        return getattr(self._original, name)


def _call_with_state(native, *args, **kwargs):
    namespace = native.__globals__.copy()
    api = namespace['api']
    ui = namespace['ui']
    native_message = ui.message
    repeat = namespace['getLastScriptRepeatCount']
    foreground = None
    firstPress = False

    def capture_foreground():
        nonlocal foreground
        foreground = api.getForegroundObject()
        return foreground

    def capture_repeat():
        nonlocal firstPress
        count = repeat()
        firstPress = count == 0
        return count

    def message(text, *messageArgs, **messageKwargs):
        nonlocal firstPress
        if firstPress:
            firstPress = False
            try:
                handle = getattr(foreground, 'windowHandle', None)
                state = get_window_state(handle) if isinstance(handle, int) and not isinstance(handle, bool) and handle > 0 else None
                labels = {'normal': _('normal'), 'maximized': _('maximized'), 'minimized': _('minimized')}
                if state in labels:
                    # Translators: window title followed by its normal/maximized/minimized state.
                    text = _('{title}, {state}').format(title=text, state=labels[state])
            except Exception:
                # Invalid handles, unavailable providers and query failures keep native text.
                pass
        # Delegate NVDA's message, not an add-on-authored priority announcement.
        return native_message(text, *messageArgs, **messageKwargs)

    namespace['api'] = _Facade(api, getForegroundObject=capture_foreground)
    namespace['ui'] = _Facade(ui, message=message)
    namespace['getLastScriptRepeatCount'] = capture_repeat
    invocation = types.FunctionType(native.__code__, namespace, native.__name__,
                                    native.__defaults__, native.__closure__)
    invocation.__kwdefaults__ = native.__kwdefaults__
    return invocation(*args, **kwargs)


class TitleWindowStateRuntime:
    _marker = '_classicSpeechTitleWindowState'

    def __init__(self, target, commands=None):
        self.target = target
        self.commands = commands
        self.original = self.wrapper = None

    def install(self):
        prior = getattr(self.target, self._marker, None)
        if prior is self:
            return
        if prior is not None:
            prior.restore()
        native = getattr(self.target, 'script_title', None)
        # Unknown wrappers/layouts fail closed; never copy/reimplement native logic.
        if not isinstance(native, types.FunctionType) or not {
            'api', 'ui', 'getLastScriptRepeatCount', 'objectBelowLockScreenAndWindowsIsLocked'
        }.issubset(native.__code__.co_names):
            return
        @functools.wraps(native)
        def wrapped(*args, **kwargs):
            if not _get_include_window_state_in_title():
                return native(*args, **kwargs)
            return _call_with_state(native, *args, **kwargs)
        self.original, self.wrapper = native, wrapped
        self.target.script_title = wrapped
        # ScriptableObject stores functions, not script names, in already-bound maps.
        for gesture, function in tuple(getattr(self.commands, '_gestureMap', {}).items()):
            if function is native:
                self.commands._gestureMap[gesture] = wrapped
        setattr(self.target, self._marker, self)

    def restore(self):
        for gesture, function in tuple(getattr(self.commands, '_gestureMap', {}).items()):
            if self.wrapper is not None and function is self.wrapper:
                self.commands._gestureMap[gesture] = self.original
        if self.wrapper is not None and getattr(self.target, 'script_title', None) is self.wrapper:
            self.target.script_title = self.original
        if getattr(self.target, self._marker, None) is self:
            delattr(self.target, self._marker)


def install():
    import globalCommands
    target = getattr(globalCommands, 'GlobalCommands', None)
    if target is None:
        return None
    runtime = TitleWindowStateRuntime(target, getattr(globalCommands, 'commands', None))
    runtime.install()
    return runtime
