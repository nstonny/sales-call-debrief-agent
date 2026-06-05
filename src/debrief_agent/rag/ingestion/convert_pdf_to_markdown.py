"""Convert one PDF file to markdown using MarkItDown with normalization.

Default paths target MEDDIC conversion into nested processed_markdown.
"""


import argparse
import importlib
import re
from pathlib import Path

DEFAULT_SOURCE_PDF_PATH = Path(
    "src/data/knowledge_base/sales_frameworks/MEDDIC_Sales_Guide.pdf"
)
DEFAULT_TARGET_MARKDOWN_PATH = Path(
    "src/data/knowledge_base/sales_frameworks/processed_markdown/MEDDIC_Sales_Guide.md"
)
DEFAULT_NORMALIZATION_PROFILE = "heading_list_table_canonical_v1"


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for one PDF -> markdown conversion."""
    parser = argparse.ArgumentParser(
        description="Convert a knowledge-base PDF to markdown with normalization."
    )
    parser.add_argument(
        "--source-pdf",
        type=Path,
        default=DEFAULT_SOURCE_PDF_PATH,
        help="Path to input PDF.",
    )
    parser.add_argument(
        "--target-markdown",
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

    titleish_ratio = sum(
        1 for word in letters_only if word.isupper() or word[0].isupper()
    ) / len(letters_only)
    return titleish_ratio >= 0.8


def _canonicalize_list_prefix(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

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


def _is_removable_page_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if re.fullmatch(r"\d+", stripped):
        return True

    lowered = stripped.lower()
    if re.fullmatch(r"(?:#+\s*)?page\s+\d+", lowered):
        return True

    if "salescoach ai" in lowered and "all rights reserved" in lowered:
        return True

    if re.fullmatch(r"(?:#+\s*)?meddic sales methodology guide", lowered):
        return True

    if "salescoach ai" in lowered and "confidential" in lowered:
        return True

    return False


def _remove_title_page_and_toc(lines: list[str]) -> list[str]:
    """Drop front-matter title page and TOC when present."""
    def _normalized_heading_text(value: str) -> str:
        return re.sub(r"^#+\s*", "", value.strip()).lower()

    toc_index = next(
        (
            idx
            for idx, line in enumerate(lines)
            if _normalized_heading_text(line) == "table of contents"
        ),
        None,
    )
    if toc_index is None:
        return lines

    for idx in range(toc_index + 1, len(lines)):
        if _normalized_heading_text(lines[idx]) != "introduction to meddic":
            continue

        window = " ".join(lines[idx + 1 : idx + 8])
        if "MEDDIC is a battle-tested" in window:
            return lines[idx:]

    # Fallback: remove everything through TOC marker.
    return lines[toc_index + 1 :]


def _normalize_markdown(markdown_text: str) -> str:
    """Canonicalize markdown and strip recurring page/header/footer artifacts."""
    source_lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

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
    run_conversion(
        source_pdf_path=args.source_pdf,
        target_markdown_path=args.target_markdown,
        normalization_profile=args.normalization_profile,
    )


if __name__ == "__main__":
    main()




