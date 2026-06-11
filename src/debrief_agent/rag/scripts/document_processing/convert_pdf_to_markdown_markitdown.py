"""Convert one PDF file to markdown using MarkItDown with normalization.

Default paths target MEDDIC conversion into nested processed_markdown.
"""


import argparse
import importlib
import re
from pathlib import Path

DEFAULT_SOURCE_PDF_PATH = Path(
    "src/data/knowledge_base/sales_frameworks/SPIN_Selling_Guide.pdf"
)
DEFAULT_TARGET_MARKDOWN_PATH = Path(
    "src/data/knowledge_base/processed_markdown/SPIN_Selling_Guide.md"
)
DEFAULT_NORMALIZATION_PROFILE = "heading_list_table_canonical_v1"
HEADING_CONNECTOR_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "vs",
    "with",
}
PAGE_ARTIFACT_REGEX = re.compile(
    r"^(?:#+\s*)?page\s+[ivxlcdm\d]+(?:\s*(?:of|/)\s*[ivxlcdm\d]+)?\s*$",
    re.IGNORECASE,
)
COPYRIGHT_LINE_REGEX = re.compile(
    r"^(?:©|copyright)\s*\d{4}.*$",
    re.IGNORECASE,
)
FOOTER_MARKER_REGEX = re.compile(
    r"\b(?:all rights reserved|internal use only|confidential|proprietary)\b",
    re.IGNORECASE,
)
ROMAN_NUMERAL_REGEX = re.compile(
    r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
    re.IGNORECASE,
)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for one PDF -> markdown conversion."""
    parser = argparse.ArgumentParser(
        description="Convert a knowledge-base PDF to markdown with normalization."
    )
    parser.add_argument(
        "source_pdf_path",
        nargs="?",
        type=Path,
        help="Path to input PDF.",
    )
    parser.add_argument(
        "target_markdown_path",
        nargs="?",
        type=Path,
        help="Path to output markdown file.",
    )
    parser.add_argument(
        "--source-pdf",
        dest="source_pdf_flag",
        type=Path,
        default=DEFAULT_SOURCE_PDF_PATH,
        help="Path to input PDF.",
    )
    parser.add_argument(
        "--target-markdown",
        dest="target_markdown_flag",
        type=Path,
        default=DEFAULT_TARGET_MARKDOWN_PATH,
        help="Path to output markdown file.",
    )
    parser.add_argument(
        "--normalization-profile",
        type=str,
        default=DEFAULT_NORMALIZATION_PROFILE,
        help="Normalization profile name.",
    )
    return parser


def _convert_with_markitdown(source_pdf_path: Path) -> str:
    module = importlib.import_module("markitdown")
    converter_class = getattr(module, "MarkItDown")
    converter = converter_class()
    result = converter.convert(str(source_pdf_path))

    text = getattr(result, "text_content", None)
    if not text:
        raise ValueError("MarkItDown returned no text content")
    return text


def _looks_like_heading(line: str) -> bool:
    if not line:
        return False
    if line.startswith("#"):
        return False
    if len(line) > 100:
        return False
    if line.endswith("."):
        return False

    if re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", line):
        return True

    words = [word for word in line.split() if word]
    if not words or len(words) > 12:
        return False

    letters_only = [re.sub(r"[^A-Za-z]", "", word) for word in words]
    letters_only = [word for word in letters_only if word]
    if not letters_only:
        return False

    # Allow lowercase connector words in title-case headings.
    non_connector_words = [
        word for word in letters_only if word.lower() not in HEADING_CONNECTOR_WORDS
    ]
    if non_connector_words:
        title_non_connector_ratio = sum(
            1 for word in non_connector_words if word.isupper() or word[0].isupper()
        ) / len(non_connector_words)
        if title_non_connector_ratio >= 0.8:
            return True

    titleish_ratio = sum(
        1 for word in letters_only if word.isupper() or word[0].isupper()
    ) / len(letters_only)
    return titleish_ratio >= 0.8


def _canonicalize_list_prefix(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    # Normalize common PDF extraction bullet artifacts.
    artifact_bullet_match = re.match(r"^(?:\(cid:127\)|ﬁ|fi|n)\s+(.+)$", stripped)
    if artifact_bullet_match:
        return f"- {artifact_bullet_match.group(1).strip()}"

    bullet_match = re.match(r"^[-*+]\s+(.+)$", stripped)
    if bullet_match:
        return f"- {bullet_match.group(1).strip()}"

    numbered_match = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
    if numbered_match:
        return f"{numbered_match.group(1)}. {numbered_match.group(2).strip()}"

    return stripped


def _normalize_table_block(lines: list[str]) -> list[str]:
    normalized_rows: list[str] = []
    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # Drop footer artifacts even when extraction wrapped them as table rows.
        row_text = " ".join(cell.strip() for cell in raw_line.strip("|").split("|"))
        if _is_removable_page_artifact(row_text):
            continue

        cells = [cell.strip() for cell in raw_line.strip("|").split("|")]
        normalized_rows.append("| " + " | ".join(cells) + " |")

    if not normalized_rows:
        return []

    if len(normalized_rows) == 1:
        return normalized_rows

    separator_regex = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
    if separator_regex.match(normalized_rows[1]):
        return normalized_rows

    header_cells = [cell.strip() for cell in normalized_rows[0].strip("|").split("|")]
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |"
    return [normalized_rows[0], separator, *normalized_rows[1:]]


def _build_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not headers or not rows:
        return []

    header = "| " + " | ".join(cell.strip() for cell in headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(cell.strip() for cell in row) + " |" for row in rows]
    return [header, separator, *body]


def _chunk_rows(values: list[str], width: int) -> list[list[str]]:
    if width <= 0 or not values or len(values) % width != 0:
        return []
    return [values[idx : idx + width] for idx in range(0, len(values), width)]


def _split_line_once(line: str, split_regex: str) -> list[str]:
    match = re.match(split_regex, line)
    if not match:
        return [line]
    return [match.group(1).strip(), match.group(2).strip()]


def _parse_six_pillars_table(section_lines: list[str]) -> list[str]:
    headers = ["Letter", "Element", "Core Question"]
    if section_lines[:3] != headers:
        return []

    remaining = section_lines[3:]
    first_column: list[str] = []
    while remaining and re.fullmatch(r"[A-Za-z]{1,2}", remaining[0]):
        first_column.append(remaining.pop(0))

    if not first_column or len(remaining) != 2 * len(first_column):
        return []

    rows = [
        [first_column[idx], remaining[2 * idx], remaining[2 * idx + 1]]
        for idx in range(len(first_column))
    ]
    return _build_markdown_table(headers, rows)


def _parse_champion_table(section_lines: list[str]) -> list[str]:
    headers = ["Role", "Definition", "What They Do For You"]
    if not section_lines or section_lines[0] != headers[0]:
        return []

    try:
        definition_idx = section_lines.index(headers[1])
        outcome_idx = section_lines.index(headers[2])
    except ValueError:
        return []

    if outcome_idx != definition_idx + 1:
        return []

    first_column = section_lines[1:definition_idx]
    if not first_column:
        return []

    remaining = section_lines[outcome_idx + 1 :]
    if len(remaining) == 2 * len(first_column) - 1 and remaining:
        split_last = _split_line_once(remaining[-1], r"^(.+?)\s+([A-Z][a-z].+)$")
        remaining = [*remaining[:-1], *split_last]

    if len(remaining) != 2 * len(first_column):
        return []

    rows = [
        [first_column[idx], remaining[2 * idx], remaining[2 * idx + 1]]
        for idx in range(len(first_column))
    ]
    return _build_markdown_table(headers, rows)


def _parse_decision_process_table(section_lines: list[str]) -> list[str]:
    headers = ["Stage", "Description / Owner / Est. Duration"]
    if section_lines[:2] != headers:
        return []
    rows = _chunk_rows(section_lines[2:], len(headers))
    return _build_markdown_table(headers, rows) if rows else []


def _parse_scoring_rubric_table(section_lines: list[str]) -> list[str]:
    headers = [
        "Element",
        "0 — Not Identified",
        "1 — Partially Known",
        "2 — Fully Qualified",
    ]
    if section_lines[:4] != headers:
        return []

    values = section_lines[4:]
    repaired_values: list[str] = []
    for value in values:
        repaired_values.extend(
            _split_line_once(value, r"^(.+?\bdiscussed)\s+(Agreed\b.+)$")
        )

    second_pass: list[str] = []
    for value in repaired_values:
        second_pass.extend(
            _split_line_once(value, r"^(.+?\bknown)\s+(Full\b.+)$")
        )

    rows = _chunk_rows(second_pass, len(headers))
    return _build_markdown_table(headers, rows) if rows else []


def _parse_best_practices_table(section_lines: list[str]) -> list[str]:
    headers = ["Stage", "MEDDIC Focus", "Key Action"]
    if section_lines[:3] != headers:
        return []
    rows = _chunk_rows(section_lines[3:], len(headers))
    return _build_markdown_table(headers, rows) if rows else []


def _rewrite_known_table_sections(source_lines: list[str]) -> list[str]:
    table_configs = {
        "The Six Pillars at a Glance": {
            "stop_at": "How to Use This Guide",
            "parser": _parse_six_pillars_table,
        },
        "Champion vs. Coach vs. Sponsor": {
            "stop_at": "How to Identify a Champion",
            "parser": _parse_champion_table,
        },
        "Decision Process Mapping Template": {
            "stop_at": "Red Flags",
            "parser": _parse_decision_process_table,
        },
        "Scoring Rubric": {
            "stop_at": "Score Interpretation",
            "parser": _parse_scoring_rubric_table,
        },
        "Best Practices by Sales Stage": {
            "stop_at": "Manager Coaching Reminders",
            "parser": _parse_best_practices_table,
        },
    }

    rewritten: list[str] = []
    idx = 0
    while idx < len(source_lines):
        current_line = source_lines[idx]
        stripped = current_line.strip()
        config = table_configs.get(stripped)
        if not config:
            rewritten.append(current_line)
            idx += 1
            continue

        stop_at = config["stop_at"]
        stop_idx = idx + 1
        while stop_idx < len(source_lines) and source_lines[stop_idx].strip() != stop_at:
            stop_idx += 1

        raw_section = source_lines[idx + 1 : stop_idx]
        section_lines = [
            line.strip()
            for line in raw_section
            if line.strip() and not _is_removable_page_artifact(line)
        ]

        table_lines = config["parser"](section_lines)
        if table_lines:
            rewritten.append(stripped)
            rewritten.append("")
            rewritten.extend(table_lines)
            rewritten.append("")
        else:
            rewritten.append(current_line)
            rewritten.extend(raw_section)

        idx = stop_idx

    return rewritten


def _is_removable_page_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if re.fullmatch(r"\d+", stripped):
        return True

    if ROMAN_NUMERAL_REGEX.fullmatch(stripped.upper()) and stripped:
        return True

    lowered = stripped.lower()
    if PAGE_ARTIFACT_REGEX.fullmatch(stripped):
        return True

    # Drop line-level page counters emitted by PDF extractors.
    if re.fullmatch(r"[ivxlcdm\d]+\s*(?:/|of)\s*[ivxlcdm\d]+", lowered):
        return True

    if COPYRIGHT_LINE_REGEX.fullmatch(stripped):
        return True

    if FOOTER_MARKER_REGEX.search(lowered) and re.search(r"\bpage\b|\d", lowered):
        return True

    if FOOTER_MARKER_REGEX.search(lowered) and "©" in stripped:
        return True

    return False


def _remove_title_page_and_toc(lines: list[str]) -> list[str]:
    """Drop front-matter title page and TOC when present."""

    def _normalized_heading_text(value: str) -> str:
        return re.sub(r"^#+\s*", "", value.strip()).lower()

    def _strip_toc_page_number(value: str) -> str:
        return re.sub(r"\s+\d+\s*$", "", value).strip()

    def _is_toc_heading_line(value: str) -> bool:
        text = _normalized_heading_text(value)
        return bool(text) and bool(re.fullmatch(r".+\s+\d+", text))

    def _strip_leading_toc_block(start_idx: int) -> list[str] | None:
        idx = start_idx
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        toc_start = idx
        while idx < len(lines) and _is_toc_heading_line(lines[idx]):
            idx += 1

        toc_block = lines[toc_start:idx]
        if len(toc_block) < 3:
            return None

        toc_titles = [
            _strip_toc_page_number(_normalized_heading_text(line)) for line in toc_block
        ]
        first_title = toc_titles[0]

        for search_idx in range(idx, len(lines)):
            candidate = _strip_toc_page_number(_normalized_heading_text(lines[search_idx]))
            if candidate == first_title:
                return lines[search_idx:]

        return None

    toc_index = next(
        (
            idx
            for idx, line in enumerate(lines)
            if _normalized_heading_text(line) == "table of contents"
        ),
        None,
    )
    if toc_index is None:
        stripped = _strip_leading_toc_block(start_idx=0)
        if stripped is not None:
            return stripped
        return lines

    for idx in range(toc_index + 1, len(lines)):
        if _normalized_heading_text(lines[idx]) != "introduction to meddic":
            continue

        window = " ".join(lines[idx + 1 : idx + 8])
        if "MEDDIC is a battle-tested" in window:
            return lines[idx:]

    stripped = _strip_leading_toc_block(start_idx=toc_index + 1)
    if stripped is not None:
        return stripped

    # Fallback: remove everything through TOC marker.
    return lines[toc_index + 1 :]


def _is_single_letter_heading(line: str) -> bool:
    return bool(re.fullmatch(r"##\s+[A-Za-z]", line.strip()))


def _normalize_markdown(markdown_text: str) -> str:
    """Canonicalize markdown and strip recurring page/header/footer artifacts."""
    source_lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    source_lines = _rewrite_known_table_sections(source_lines)

    normalized_lines: list[str] = []
    idx = 0
    while idx < len(source_lines):
        line = source_lines[idx]
        stripped = line.strip()

        if _is_removable_page_artifact(stripped):
            idx += 1
            continue

        if stripped.count("|") >= 2:
            table_block: list[str] = [stripped]
            idx += 1
            while idx < len(source_lines) and source_lines[idx].strip().count("|") >= 2:
                table_block.append(source_lines[idx].strip())
                idx += 1
            normalized_lines.extend(_normalize_table_block(table_block))
            continue

        if not stripped:
            normalized_lines.append("")
            idx += 1
            continue

        normalized = _canonicalize_list_prefix(line)
        if _looks_like_heading(normalized):
            normalized = f"## {normalized.rstrip(':')}"
        if _is_single_letter_heading(normalized):
            idx += 1
            continue
        normalized_lines.append(normalized)
        idx += 1

    normalized_lines = _remove_title_page_and_toc(normalized_lines)

    compact_lines: list[str] = []
    blank_streak = 0
    for line in normalized_lines:
        if line.strip():
            blank_streak = 0
            compact_lines.append(line)
            continue

        blank_streak += 1
        if blank_streak <= 1:
            compact_lines.append("")

    return "\n".join(compact_lines).strip() + "\n"


def run_conversion(
    source_pdf_path: Path,
    target_markdown_path: Path,
    normalization_profile: str,
) -> None:
    """Convert and normalize one PDF into markdown output."""
    if normalization_profile != DEFAULT_NORMALIZATION_PROFILE:
        raise ValueError(
            "Unsupported normalization profile: "
            f"{normalization_profile}. Expected {DEFAULT_NORMALIZATION_PROFILE}."
        )

    markdown_raw = _convert_with_markitdown(source_pdf_path)
    markdown_normalized = _normalize_markdown(markdown_raw)

    target_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    target_markdown_path.write_text(markdown_normalized, encoding="utf-8")

    print(f"Source PDF: {source_pdf_path}")
    print(f"Target markdown: {target_markdown_path}")
    print(f"Normalization profile: {normalization_profile}")
    print(f"Wrote {len(markdown_normalized)} characters")


def main() -> None:
    """Parse args and run conversion."""
    args = build_parser().parse_args()

    source_pdf_path = args.source_pdf_path or args.source_pdf_flag
    target_markdown_path = args.target_markdown_path or args.target_markdown_flag

    run_conversion(
        source_pdf_path=source_pdf_path,
        target_markdown_path=target_markdown_path,
        normalization_profile=args.normalization_profile,
    )


if __name__ == "__main__":
    main()





