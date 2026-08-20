# ClassicSpeech Localization Foundation Implementation Plan

> **For Hermes:** Execute this plan task-by-task and verify each milestone.

**Goal:** Make ClassicSpeech user-facing dialog and spoken text translatable through NVDA's active interface language, with an independent Spanish catalog ready for Luis to complete.

**Architecture:** Add a small `_speech_core.localization` adapter that loads the add-on gettext domain when ClassicSpeech is installed, falls back to NVDA's installed translator for exact shared strings, and remains safe when running from NVDA Scratchpad or test harnesses. Keep internal configuration keys and matching constants untranslated. Package the `locale` tree at the add-on root.

**Tech Stack:** Python 3.11, NVDA add-on gettext support, GNU PO/MO files, existing unittest-style harnesses, ZIP add-on packaging.

---

### Task 1: Define localization contracts

**Files:**
- Create: `tests/classic_speech_localization_harness.py`
- Modify: `tests/classic_speech_packaging_harness.py`

**Steps:**
1. Test add-on translation precedence, NVDA-core fallback, and identity fallback.
2. Test that Scratchpad/no-add-on execution never raises.
3. Test that translated display choices remain separate from stable internal values.
4. Test that packaging includes Spanish manifest and MO files at `locale/es/...`.
5. Run both focused harnesses and confirm the new tests fail before implementation.

### Task 2: Add the Scratchpad-safe localization adapter

**Files:**
- Create: `_speech_core/localization.py`

**Steps:**
1. Load ClassicSpeech's `nvda` gettext domain through `addonHandler.getCodeAddon` when available.
2. Fall back to NVDA's installed translation functions for missing entries.
3. Fall back to the original English string when neither catalog has an entry.
4. Expose `_`, `pgettext`, `ngettext`, and `npgettext` without modifying global builtins.
5. Run the focused localization harness.

### Task 3: Mark user-facing text

**Files:**
- Modify: `classicSpeech.py`
- Modify: user-interface and spoken-feedback modules under `_speech_core/`

**Steps:**
1. Import the localization adapter in modules with user-facing text.
2. Wrap dialog titles, category names, control labels, choices, button labels, descriptions, messages, and gesture descriptions.
3. Keep machine identifiers, configuration values, Edge activity matching strings, and log text untranslated.
4. Where code maps selection indexes to constants, translate only the displayed list.
5. Compile every changed Python file and run relevant settings/speech harnesses.

### Task 4: Add translation source and packaging

**Files:**
- Create: `locale/classicspeech.pot`
- Create: `locale/es/LC_MESSAGES/nvda.po`
- Create: `locale/es/LC_MESSAGES/nvda.mo`
- Create: `locale/es/manifest.ini`
- Create or modify: extraction/compilation helper under `scripts/`
- Modify: `scripts/package_addon.py`

**Steps:**
1. Extract marked strings deterministically into a POT template.
2. Seed only exact, context-safe Spanish matches from NVDA's catalog; leave ClassicSpeech-specific entries empty for Luis.
3. Compile and validate the MO file.
4. Package the locale tree at the add-on root.
5. Verify archive paths and translation lookup with focused tests.

### Task 5: Verification

**Steps:**
1. Run Python compilation for all runtime modules.
2. Run the localization and packaging harnesses.
3. Run every `tests/*_harness.py` file.
4. Build a test add-on and inspect its archive members.
5. Report static verification separately from live NVDA validation; do not deploy or restart NVDA without Tim's explicit request.
