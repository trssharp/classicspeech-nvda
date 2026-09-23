"""Focused contracts for ClassicSpeech localization behavior."""
from __future__ import annotations

import builtins
import gettext
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LOCALIZATION = ROOT / "_speech_core" / "localization.py"
SPANISH_CATALOG = ROOT / "locale" / "es" / "LC_MESSAGES" / "nvda.mo"
TRANSLATION_SCRIPT = ROOT / "scripts" / "update_translations.py"


class _FakeTranslations:
    def __init__(self, messages=None, contextual=None):
        self.messages = dict(messages or {})
        self.contextual = dict(contextual or {})

    def gettext(self, message):
        return self.messages.get(message, message)

    def pgettext(self, context, message):
        return self.contextual.get((context, message), message)

    def ngettext(self, singular, plural, count):
        message = singular if count == 1 else plural
        return self.messages.get(message, message)

    def npgettext(self, context, singular, plural, count):
        message = singular if count == 1 else plural
        return self.contextual.get((context, message), message)


def _load_localization(addon_translation=None, addon_error=None):
    addon_handler = ModuleType("addonHandler")

    def get_code_addon():
        if addon_error is not None:
            raise addon_error
        return SimpleNamespace(getTranslationsInstance=lambda: addon_translation)

    addon_handler.getCodeAddon = get_code_addon
    spec = importlib.util.spec_from_file_location("classicspeech_localization_test", LOCALIZATION)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"addonHandler": addon_handler}):
        spec.loader.exec_module(module)
    return module


def _load_translation_script():
    spec = importlib.util.spec_from_file_location("classicspeech_translation_script_test", TRANSLATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LocalizationTests(unittest.TestCase):
    def test_visible_reviewed_strings_are_extractable_literals(self):
        messages = {
            key.singular
            for key in _load_translation_script().extract_messages()
        }
        for expected in (
            "Font",
            "&Font name",
            "Pages and spacing",
            "Table information",
            "Default button {name}",
            "{tokenLabel} pause:",
            "NVDA native",
            "copied",
            "unknown",
        ):
            self.assertIn(expected, messages)

    def test_plural_catalog_preserves_both_spanish_forms(self):
        script = _load_translation_script()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            po_path = root / "es" / "LC_MESSAGES" / "nvda.po"
            mo_path = po_path.with_suffix(".mo")
            po_path.parent.mkdir(parents=True)
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Language: es\\n"\n'
                '"Content-Type: text/plain; charset=UTF-8\\n"\n'
                '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
                'msgid "item"\n'
                'msgid_plural "items"\n'
                'msgstr[0] "elemento"\n'
                'msgstr[1] "elementos"\n',
                encoding="utf-8",
            )
            script.compile_mo(po_path, mo_path)
            with mo_path.open("rb") as catalog_file:
                translations = gettext.GNUTranslations(catalog_file)
        self.assertEqual(translations.ngettext("item", "items", 1), "elemento")
        self.assertEqual(translations.ngettext("item", "items", 2), "elementos")

    def test_compiled_spanish_catalog_loads_and_falls_back_per_message(self):
        with SPANISH_CATALOG.open("rb") as catalog_file:
            translations = gettext.GNUTranslations(catalog_file)
        self.assertEqual(translations.gettext("Cancel"), "Cancelar")
        self.assertEqual(
            translations.gettext("Page summary is not available here."),
            "El resumen de página no está disponible aquí.",
        )

    def test_every_spanish_po_entry_matches_the_runtime_catalog(self):
        script = _load_translation_script()
        entries = script.parse_po(SPANISH_CATALOG.with_suffix(".po"))
        with SPANISH_CATALOG.open("rb") as catalog_file:
            translations = gettext.GNUTranslations(catalog_file)
        for key, expected in entries.items():
            if not script._has_translation(expected):
                continue
            with self.subTest(message=key.singular, context=key.context):
                if key.plural:
                    for count, form in ((1, 0), (2, 1)):
                        actual = (
                            translations.npgettext(key.context, key.singular, key.plural, count)
                            if key.context else translations.ngettext(key.singular, key.plural, count)
                        )
                        self.assertEqual(actual, expected[form])
                else:
                    actual = (
                        translations.pgettext(key.context, key.singular)
                        if key.context else translations.gettext(key.singular)
                    )
                    self.assertEqual(actual, expected)

    def test_spanish_scheme_dialog_accelerators_are_unique(self):
        import ast
        import re

        script = _load_translation_script()
        entries = script.parse_po(SPANISH_CATALOG.with_suffix(".po"))
        labels = set()
        for filename in ("schemes_dialog.py", "schemes_panel.py"):
            tree = ast.parse((ROOT / "_speech_core" / "settings" / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "_" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str) and "&" in node.args[0].value):
                    labels.add(node.args[0].value)
        # This alternative tree label is displayed only in the Voice Profiles dialog.
        labels.remove("Document and web formatting &items:")
        used = {}
        for label in sorted(labels):
            translated = entries[script.MessageKey("", label)]
            keys = re.findall(r"(?<!&)&([^&])", translated)
            self.assertEqual(len(keys), 1, (label, translated))
            key = keys[0].casefold()
            self.assertNotIn(key, used, (translated, used.get(key)))
            used[key] = translated

    def test_spanish_sound_modes_refer_to_messages_not_descriptions(self):
        with SPANISH_CATALOG.open("rb") as catalog_file:
            translations = gettext.GNUTranslations(catalog_file)
        self.assertEqual(translations.gettext("Also speak the announcement"), "Anunciar también el mensaje")
        self.assertEqual(
            translations.gettext("Do not speak the announcement (sound only)"),
            "No anunciar el mensaje (solo sonido)",
        )

    def test_spanish_reviewed_meaning_corrections(self):
        with SPANISH_CATALOG.open("rb") as catalog_file:
            translations = gettext.GNUTranslations(catalog_file)
        expected = {
            "Abbreviated without plus": "Abreviado sin signos más",
            "Expanded without plus": "Expandido sin signos más",
            "Clear Rename\tDelete": "Borrar nombre personalizado\tSuprimir",
            "Navigator object": "Navegador de objetos",
            "No selected element types found.": "No se encontraron elementos de los tipos seleccionados.",
            "Reports selected Browse Mode element counts for the current page":
                "Anuncia el número de elementos de los tipos seleccionados en el modo de exploración para la página actual",
            "Suppress dashes inside words, such as sister-in-law":
                "Suprimir guiones dentro de palabras, como sister-in-law",
            "Reset all Voice Profile overrides":
                "Restablecer todos los ajustes personalizados de los perfiles de voz",
        }
        for source, spanish in expected.items():
            with self.subTest(source=source):
                self.assertEqual(translations.gettext(source), spanish)
        entries = _load_translation_script().parse_po(SPANISH_CATALOG.with_suffix(".po"))
        for key in entries:
            if "saved overrides" in key.singular or "Voice Profile override" in key.singular:
                with self.subTest(source=key.singular):
                    self.assertIn("ajustes personalizados", translations.gettext(key.singular))
            if key.singular.startswith("Key labels control"):
                self.assertIn("borrar el nombre personalizado", translations.gettext(key.singular))
            if key.singular.startswith("NVDA native is the safe default"):
                translated = translations.gettext(key.singular)
                self.assertIn("«one eight hundred» (uno ochocientos)", translated)
                self.assertNotIn("vigésimo-segundo", translated)

    def test_addon_translation_takes_precedence(self):
        addon_translation = _FakeTranslations({"Cancel": "Cancelar desde ClassicSpeech"})
        with mock.patch.object(builtins, "_", return_value="Cancelar desde NVDA", create=True):
            localization = _load_localization(addon_translation)
            self.assertEqual(localization._("Cancel"), "Cancelar desde ClassicSpeech")

    def test_missing_addon_entry_uses_nvda_translation(self):
        addon_translation = _FakeTranslations()
        with mock.patch.object(builtins, "_", side_effect=lambda message: {"Cancel": "Cancelar"}.get(message, message), create=True):
            localization = _load_localization(addon_translation)
            self.assertEqual(localization._("Cancel"), "Cancelar")
            self.assertEqual(localization._("ClassicSpeech-only text"), "ClassicSpeech-only text")

    def test_scratchpad_mode_falls_back_without_raising(self):
        with mock.patch.object(builtins, "_", side_effect=lambda message: {"Close": "Cerrar"}.get(message, message), create=True):
            localization = _load_localization(addon_error=RuntimeError("not installed as an add-on"))
            self.assertEqual(localization._("Close"), "Cerrar")
            self.assertEqual(localization._("Unique text"), "Unique text")

    def test_context_and_plural_functions_follow_the_same_fallback_order(self):
        addon_translation = _FakeTranslations(contextual={("button", "Close"): "Cerrar panel"})
        with mock.patch.object(builtins, "pgettext", side_effect=lambda context, message: f"NVDA:{context}:{message}", create=True), mock.patch.object(
            builtins,
            "ngettext",
            side_effect=lambda singular, plural, count: "elemento" if count == 1 else "elementos",
            create=True,
        ):
            localization = _load_localization(addon_translation)
            self.assertEqual(localization.pgettext("button", "Close"), "Cerrar panel")
            self.assertEqual(localization.pgettext("menu", "Close"), "NVDA:menu:Close")
            self.assertEqual(localization.ngettext("item", "items", 2), "elementos")


if __name__ == "__main__":
    unittest.main()
