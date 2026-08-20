# ClassicSpeech translations

ClassicSpeech follows NVDA's active interface language. It does not add a separate language setting and does not use an online translation service.

## Spanish translation

The editable Spanish catalog is:

`locale/es/LC_MESSAGES/nvda.po`

Each entry contains the original English text in `msgid`. Add the reviewed Spanish text to `msgstr` without changing format placeholders such as `{profile}`, `{display}`, `{text}`, or `{ms}`.

Example:

```po
msgid "Page summary is not available here."
msgstr "El resumen de la página no está disponible aquí."
```

The current catalog contains a small reviewed seed of exact, context-safe strings from NVDA. All seeded entries still require translator review. Blank entries are deliberately left in English at runtime until translated.

## Refresh and compile

From the repository root, run:

```text
python scripts/update_translations.py --language es
```

This command:

1. Extracts marked ClassicSpeech strings into `locale/classicspeech.pot`.
2. Preserves existing Spanish translations.
3. Updates `locale/es/LC_MESSAGES/nvda.po`.
4. Compiles the runtime catalog as `locale/es/LC_MESSAGES/nvda.mo`.

To seed a new catalog from an NVDA source checkout, pass its PO file explicitly:

```text
python scripts/update_translations.py --language es --seed-po "path/to/nvda/source/locale/es/LC_MESSAGES/nvda.po"
```

Only strings in the script's reviewed allowlist are imported. Exact spelling alone is not enough; context and accelerator markers must also be safe.

## Packaging

The add-on package includes compiled `.mo` catalogs. Editable `.po` and `.pot` sources remain in the repository and are intentionally excluded from the `.nvda-addon` archive.
