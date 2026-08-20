"""ClassicSpeech translation helpers with NVDA and Scratchpad fallbacks.

Installed add-ons load their own ``nvda`` gettext domain. Missing add-on
entries fall back to NVDA's active interface translation, which is installed
in :mod:`builtins`. Scratchpad and standalone test runs safely use the same
NVDA/English fallback without requiring an Addon object.
"""
from __future__ import annotations

import builtins
import gettext
from collections.abc import Callable


def _load_addon_translations():
    try:
        import addonHandler

        addon = addonHandler.getCodeAddon()
        translations = addon.getTranslationsInstance()
        if translations is not None:
            return translations
    except Exception:
        # getCodeAddon intentionally fails for Scratchpad modules and standalone
        # harnesses. Localization must never prevent ClassicSpeech from loading.
        pass
    return gettext.NullTranslations()


_ADDON_TRANSLATIONS = _load_addon_translations()


def _core_function(name: str, fallback: Callable):
    function = getattr(builtins, name, None)
    return function if callable(function) else fallback


def _(message: str) -> str:
    """Translate a message through ClassicSpeech, then NVDA, then English."""
    translated = _ADDON_TRANSLATIONS.gettext(message)
    if translated != message:
        return translated
    return _core_function("_", lambda value: value)(message)


def pgettext(context: str, message: str) -> str:
    """Translate a contextual message with the standard fallback order."""
    translated = _ADDON_TRANSLATIONS.pgettext(context, message)
    if translated != message:
        return translated
    return _core_function("pgettext", lambda _context, value: value)(context, message)


def ngettext(singular: str, plural: str, count: int) -> str:
    """Translate a plural message with the standard fallback order."""
    translated = _ADDON_TRANSLATIONS.ngettext(singular, plural, count)
    untranslated = singular if count == 1 else plural
    if translated != untranslated:
        return translated
    return _core_function(
        "ngettext",
        lambda one, many, number: one if number == 1 else many,
    )(singular, plural, count)


def npgettext(context: str, singular: str, plural: str, count: int) -> str:
    """Translate a contextual plural message with the standard fallback order."""
    translated = _ADDON_TRANSLATIONS.npgettext(context, singular, plural, count)
    untranslated = singular if count == 1 else plural
    if translated != untranslated:
        return translated
    return _core_function(
        "npgettext",
        lambda _context, one, many, number: one if number == 1 else many,
    )(context, singular, plural, count)
