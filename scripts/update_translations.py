"""Extract ClassicSpeech gettext strings and compile a language catalog."""
from __future__ import annotations

import argparse
import ast
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (ROOT / "classicSpeech.py",)
SOURCE_DIRECTORIES = (ROOT / "_speech_core",)
NVDA_SEED_ALLOWLIST = frozenset(
    {
        "Advanced",
        "Browse Mode",
        "Cancel",
        "Close",
        "No focus",
        "OK",
        "Off",
        "block quote",
        "button",
        "check box",
        "combo box",
        "embedded object",
        "frame",
        "graphic",
        "heading",
        "landmark",
        "link",
        "list",
        "radio button",
        "separator",
        "table",
    }
)


@dataclass(frozen=True, order=True)
class MessageKey:
    context: str
    singular: str
    plural: str = ""


TranslationValue = str | tuple[str, ...]


def _has_translation(value: TranslationValue | None) -> bool:
    if isinstance(value, tuple):
        return bool(value) and all(value)
    return bool(value)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def extract_messages() -> dict[MessageKey, set[str]]:
    messages: dict[MessageKey, set[str]] = {}
    paths = list(SOURCE_FILES)
    for directory in SOURCE_DIRECTORIES:
        paths.extend(sorted(directory.rglob("*.py")))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            key = None
            if name == "_" and node.args and isinstance(node.args[0], ast.Constant):
                key = MessageKey("", node.args[0].value)
            elif name == "pgettext" and len(node.args) >= 2 and all(
                isinstance(argument, ast.Constant) for argument in node.args[:2]
            ):
                key = MessageKey(node.args[0].value, node.args[1].value)
            elif name == "ngettext" and len(node.args) >= 2 and all(
                isinstance(argument, ast.Constant) for argument in node.args[:2]
            ):
                key = MessageKey("", node.args[0].value, node.args[1].value)
            elif name == "npgettext" and len(node.args) >= 3 and all(
                isinstance(argument, ast.Constant) for argument in node.args[:3]
            ):
                key = MessageKey(node.args[0].value, node.args[1].value, node.args[2].value)
            if key is not None and isinstance(key.singular, str) and key.singular:
                reference = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
                messages.setdefault(key, set()).add(reference)
    return messages


def parse_po(path: Path) -> dict[MessageKey, TranslationValue]:
    if not path.is_file():
        return {}
    entries: dict[MessageKey, TranslationValue] = {}
    current: dict[str, object] = {}
    field = ""
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines() + [""]:
        if raw_line.startswith("msgctxt "):
            field = "context"
            current[field] = ast.literal_eval(raw_line[8:])
        elif raw_line.startswith("msgid_plural "):
            field = "plural"
            current[field] = ast.literal_eval(raw_line[13:])
        elif raw_line.startswith("msgid "):
            field = "singular"
            current[field] = ast.literal_eval(raw_line[6:])
        elif raw_line.startswith("msgstr "):
            field = "translation"
            current[field] = ast.literal_eval(raw_line[7:])
        elif plural_match := re.match(r"msgstr\[(\d+)\]\s+(.*)$", raw_line):
            plural_index = int(plural_match.group(1))
            field = f"translation_{plural_index}"
            current[field] = ast.literal_eval(plural_match.group(2))
        elif raw_line.startswith('"') and field:
            current[field] = str(current.get(field, "")) + ast.literal_eval(raw_line)
        elif not raw_line.strip():
            singular = str(current.get("singular", ""))
            if singular:
                key = MessageKey(
                    str(current.get("context", "")),
                    singular,
                    str(current.get("plural", "")),
                )
                if key.plural:
                    plural_indices = sorted(
                        int(name.removeprefix("translation_"))
                        for name in current
                        if name.startswith("translation_")
                    )
                    entries[key] = tuple(
                        str(current.get(f"translation_{index}", ""))
                        for index in range((plural_indices[-1] + 1) if plural_indices else 2)
                    )
                else:
                    entries[key] = str(current.get("translation", ""))
            current = {}
            field = ""
        elif not raw_line.startswith("#"):
            field = ""
    return entries


def render_po(
    messages: dict[MessageKey, set[str]],
    translations: dict[MessageKey, TranslationValue],
    language: str,
) -> str:
    lines = [
        '# ClassicSpeech translations.',
        'msgid ""',
        'msgstr ""',
        f'"Language: {language}\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"',
        "",
    ]
    for key in sorted(messages):
        references = " ".join(sorted(messages[key]))
        lines.append(f"#: {references}")
        if key.context:
            lines.append(f"msgctxt {_quoted(key.context)}")
        lines.append(f"msgid {_quoted(key.singular)}")
        if key.plural:
            value = translations.get(key, ())
            forms = value if isinstance(value, tuple) else ((value,) if value else ())
            lines.append(f"msgid_plural {_quoted(key.plural)}")
            lines.append(f"msgstr[0] {_quoted(forms[0] if len(forms) > 0 else '')}")
            lines.append(f"msgstr[1] {_quoted(forms[1] if len(forms) > 1 else '')}")
        else:
            value = translations.get(key, "")
            lines.append(f"msgstr {_quoted(value if isinstance(value, str) else '')}")
        lines.append("")
    return "\n".join(lines)


def compile_mo(po_path: Path, mo_path: Path) -> None:
    translations = parse_po(po_path)
    catalog = {
        "": (
            f"Language: {po_path.parents[1].name}\n"
            "Content-Type: text/plain; charset=UTF-8\n"
            "Content-Transfer-Encoding: 8bit\n"
            "Plural-Forms: nplurals=2; plural=(n != 1);\n"
        )
    }
    for key, translation in translations.items():
        original = key.singular
        if key.context:
            original = f"{key.context}\x04{original}"
        if key.plural:
            if not isinstance(translation, tuple) or not translation or not all(translation):
                continue
            original = f"{original}\0{key.plural}"
            catalog[original] = "\0".join(translation)
        else:
            if not isinstance(translation, str) or not translation:
                continue
            catalog[original] = translation

    originals = sorted(catalog)
    encoded_originals = [value.encode("utf-8") for value in originals]
    encoded_translations = [catalog[value].encode("utf-8") for value in originals]
    count = len(originals)
    original_table_offset = 7 * 4
    translation_table_offset = original_table_offset + count * 8
    string_offset = translation_table_offset + count * 8

    original_data = b""
    original_table = []
    cursor = string_offset
    for value in encoded_originals:
        original_table.append((len(value), cursor))
        original_data += value + b"\0"
        cursor += len(value) + 1

    translation_data = b""
    translation_table = []
    cursor = string_offset + len(original_data)
    for value in encoded_translations:
        translation_table.append((len(value), cursor))
        translation_data += value + b"\0"
        cursor += len(value) + 1

    output = struct.pack(
        "<7I",
        0x950412DE,
        0,
        count,
        original_table_offset,
        translation_table_offset,
        0,
        0,
    )
    output += b"".join(struct.pack("<2I", *entry) for entry in original_table)
    output += b"".join(struct.pack("<2I", *entry) for entry in translation_table)
    output += original_data + translation_data
    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", default="es")
    parser.add_argument("--seed-po", type=Path)
    args = parser.parse_args()

    messages = extract_messages()
    template_path = ROOT / "locale" / "classicspeech.pot"
    language_path = ROOT / "locale" / args.language / "LC_MESSAGES" / "nvda.po"
    compiled_path = language_path.with_suffix(".mo")

    existing = parse_po(language_path)
    seeds = parse_po(args.seed_po) if args.seed_po else {}
    translations: dict[MessageKey, TranslationValue] = {}
    for key in messages:
        existing_value = existing.get(key)
        seed_value = (
            seeds.get(key)
            if not key.context and key.singular in NVDA_SEED_ALLOWLIST
            else None
        )
        if _has_translation(existing_value):
            translations[key] = existing_value
        elif _has_translation(seed_value):
            translations[key] = seed_value
        else:
            translations[key] = ("", "") if key.plural else ""

    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(render_po(messages, {}, ""), encoding="utf-8", newline="\n")
    language_path.parent.mkdir(parents=True, exist_ok=True)
    language_path.write_text(
        render_po(messages, translations, args.language),
        encoding="utf-8",
        newline="\n",
    )
    compile_mo(language_path, compiled_path)

    translated = sum(_has_translation(value) for value in translations.values())
    print(f"MESSAGES={len(messages)}")
    print(f"TRANSLATED={translated}")
    print(f"POT={template_path}")
    print(f"PO={language_path}")
    print(f"MO={compiled_path}")


if __name__ == "__main__":
    main()
