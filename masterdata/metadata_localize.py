#!/usr/bin/env python3
"""Export and apply translations in Unity IL2CPP global-metadata.dat files.

The script keeps string indices stable and never overwrites the input metadata
file.  It is intended to be run on a computer; the metadata can come from an
Android APK or an iOS IPA.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


# Hiragana, Katakana, Katakana phonetic extensions, and half-width Katakana.
KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]")
# CJK Unified Ideographs and Extension A.  Han characters alone are ambiguous
# between Chinese and Japanese, so callers can disable this range.
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def contains_japanese(value: str, *, include_han: bool = True) -> bool:
    """Return whether *value* contains Japanese kana or (optionally) Han."""

    if KANA_RE.search(value):
        return True
    return include_han and bool(HAN_RE.search(value))


def make_translation_entries(
    strings: Iterable[dict[str, Any]], *, include_han: bool = True
) -> list[dict[str, Any]]:
    """Build a stable-index translation template from Meta String Editor JSON."""

    result: list[dict[str, Any]] = []
    for item in strings:
        value = str(item.get("value", ""))
        if contains_japanese(value, include_han=include_han):
            result.append(
                {
                    "nth": int(item["nth"]),
                    "source": value,
                    "translation": "",
                }
            )
    return result


def translation_value(entry: dict[str, Any]) -> str | None:
    """Read a translated value, treating an empty field as 'leave unchanged'."""

    for key in ("translation", "translated"):
        if key in entry:
            value = entry[key]
            return None if value in (None, "") else str(value)

    # Also accept a hand-edited object containing {nth, source, value}.
    if "source" in entry and "value" in entry:
        value = entry["value"]
        if value != entry["source"] and value not in (None, ""):
            return str(value)
    return None


def find_duplicate_values(strings: Iterable[tuple[int, str]]) -> dict[str, list[int]]:
    """Return string values that occur at more than one metadata index."""

    indices_by_value: dict[str, list[int]] = {}
    for nth, value in strings:
        indices_by_value.setdefault(value, []).append(int(nth))
    return {
        value: indices
        for value, indices in indices_by_value.items()
        if len(indices) > 1
    }


def console_safe_text(value: str) -> str:
    """Make an error message safe for legacy non-UTF-8 Windows consoles."""

    return value.encode("ascii", errors="backslashreplace").decode("ascii")


def _add_local_binding_path() -> None:
    """Prefer a metastringedit package beside the script or current workspace."""

    script_dir = Path(__file__).resolve().parent
    candidates = (
        Path.cwd() / ".tools" / "metastringedit",
        Path.cwd() / "metastringedit",
        script_dir / ".tools" / "metastringedit",
        script_dir / "metastringedit",
    )
    for candidate in candidates:
        if (candidate / "metastringedit").is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
            return


def _load_metadata_function():
    _add_local_binding_path()
    try:
        from metastringedit import load_metadata
    except Exception as exc:  # pragma: no cover - depends on the host install
        raise RuntimeError(
            "找不到 metastringedit Python 绑定。请先执行: pip install metastringedit"
        ) from exc
    return load_metadata


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _string_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("strings"), list):
        return data["strings"]
    raise ValueError("JSON 必须是字符串数组，或包含 strings 数组的对象")


def export_metadata(metadata_path: Path, output_dir: Path, *, include_han: bool) -> None:
    """Export all strings and Japanese translation templates."""

    load_metadata = _load_metadata_function()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_path = output_dir / "all-strings.json"

    with load_metadata(metadata_path) as metadata:
        metadata.export_json(all_path)
        info = {
            "metadata_version": metadata.get_version(),
            "file_size": metadata.get_file_size(),
            "string_count": metadata.get_string_count(),
        }

    # Re-encode the tool output as UTF-8 without ASCII escaping, so it is easy
    # to read and edit in any modern text editor.
    strings = _string_list(_read_json(all_path))
    _write_json(all_path, strings)

    japanese = make_translation_entries(strings, include_han=include_han)
    kana_only = make_translation_entries(strings, include_han=False)
    _write_json(output_dir / "japanese-strings.json", japanese)
    _write_json(output_dir / "japanese-kana-only.json", kana_only)
    _write_json(output_dir / "metadata-info.json", info)

    han_only_count = len(japanese) - len(kana_only) if include_han else 0
    print(f"Metadata version: {info['metadata_version']}")
    print(f"All strings: {len(strings)}")
    print(f"Japanese candidates: {len(japanese)}")
    print(f"Kana-containing strings: {len(kana_only)}")
    if include_han:
        print(f"Han-only candidates to review: {han_only_count}")
    print(f"Output directory: {output_dir}")


def _translation_entries(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("strings"), list):
        return data["strings"]
    raise ValueError("翻译 JSON 必须是数组，或包含 strings 数组的对象")


def apply_translations(
    metadata_path: Path,
    translations_path: Path,
    output_path: Path,
    *,
    source_check: bool = True,
    reject_duplicate_values: bool = True,
) -> None:
    """Apply non-empty translations to a new metadata file."""

    if metadata_path.resolve() == output_path.resolve():
        raise ValueError("输出文件不能覆盖输入 metadata；请指定一个新文件名")

    entries = _translation_entries(_read_json(translations_path))
    load_metadata = _load_metadata_function()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    applied = 0
    skipped = 0
    with load_metadata(metadata_path) as metadata:
        current_strings = {item.nth: item.value for item in metadata.list_strings()}
        for entry in entries:
            if "nth" not in entry:
                raise ValueError("翻译条目缺少 nth 字段")
            nth = int(entry["nth"])
            replacement = translation_value(entry)
            if replacement is None:
                skipped += 1
                continue

            if nth not in current_strings:
                raise ValueError(f"字符串索引不存在: {nth}")
            if source_check and "source" in entry and entry["source"] != current_strings[nth]:
                raise ValueError(
                    f"索引 {nth} 的源文本不匹配；请确认翻译文件和 metadata 来自同一版本"
                )
            metadata.modify_string(nth, replacement)
            applied += 1

        if reject_duplicate_values:
            duplicates = find_duplicate_values(
                (item.nth, item.value) for item in metadata.list_strings()
            )
            if duplicates:
                examples = []
                for value, indices in list(duplicates.items())[:5]:
                    compact_value = value.replace("\n", "\\n")
                    if len(compact_value) > 40:
                        compact_value = compact_value[:37] + "..."
                    examples.append(f"{compact_value!r} -> {indices}")
                raise ValueError(
                    "翻译后 metadata 存在重复字符串值，可能导致客户端重复键崩溃: "
                    + "; ".join(examples)
                )

        metadata.save(output_path)

    print(f"Applied translations: {applied}")
    print(f"Skipped empty translations: {skipped}")
    print(f"Output metadata: {output_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Japanese strings from, or apply translations to, global-metadata.dat"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export", help="export all strings and a Japanese translation template"
    )
    export_parser.add_argument("metadata", type=Path, help="global-metadata.dat")
    export_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("metadata_translation"),
        help="output directory (default: metadata_translation)",
    )
    export_parser.add_argument(
        "--kana-only",
        action="store_true",
        help="put only kana-containing strings in japanese-strings.json",
    )

    apply_parser = subparsers.add_parser(
        "apply", help="apply translations to a new metadata file"
    )
    apply_parser.add_argument("metadata", type=Path, help="原始 global-metadata.dat")
    apply_parser.add_argument("translations", type=Path, help="japanese-strings.json")
    apply_parser.add_argument("output", type=Path, help="新的 global-metadata.dat")
    apply_parser.add_argument(
        "--no-source-check",
        action="store_true",
        help="skip source-field validation (not recommended)",
    )
    apply_parser.add_argument(
        "--allow-duplicate-values",
        action="store_true",
        help="write duplicate string values anyway (not recommended)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "export":
            export_metadata(args.metadata, args.out_dir, include_han=not args.kana_only)
        else:
            apply_translations(
                args.metadata,
                args.translations,
                args.output,
                source_check=not args.no_source_check,
                reject_duplicate_values=not args.allow_duplicate_values,
            )
    except Exception as exc:
        print(f"错误: {console_safe_text(str(exc))}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
