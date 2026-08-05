"""Convert one PDF file to markdown using MarkItDown with normalization.

Default paths target Sales_Playbook conversion into company_playbooks.
Sales-framework PDFs (SPIN, MEDDIC) should target sales_frameworks/.
"""


import argparse
import importlib
import re
from pathlib import Path

DEFAULT_SOURCE_PDF_PATH = Path(
    "src/data/knowledge_base/company_playbooks/Sales_Playbook.pdf"
)
DEFAULT_TARGET_MARKDOWN_PATH = Path(
    "src/data/knowledge_base/company_playbooks/Sales_Playbook.md"
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
    """Parse The Six Pillars at a Glance into table format.

    Expected pattern in section_lines:
    - Lines alternate between MEDDIC element names and their core questions
    - Single letter indicators (M, E, D, D, I, C) may or may not be present
    """
    headers = ["Letter", "Element", "Core Question"]

    # Define the expected MEDDIC elements in order
    meddic_elements = [
        ("M", "Metrics"),
        ("E", "Economic Buyer"),
        ("D", "Decision Criteria"),
        ("D", "Decision Process"),
        ("I", "Identify Pain"),
        ("C", "Champion"),
    ]

    rows: list[list[str]] = []
    i = 0
    element_idx = 0

    while i < len(section_lines) and element_idx < len(meddic_elements):
        line = section_lines[i].strip()
        letter, element = meddic_elements[element_idx]

        # Check if current line matches expected element
        if element.lower() in line.lower() or line == element:
            # Next line should be the core question
            if i + 1 < len(section_lines):
                question = section_lines[i + 1].strip()
                rows.append([letter, element, question])
                i += 2
                element_idx += 1
            else:
                i += 1
        else:
            i += 1

    # Only return table if we found all 6 MEDDIC elements
    if len(rows) == 6:
        return _build_markdown_table(headers, rows)

    return []


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


def _parse_types_of_metrics_table(section_lines: list[str]) -> list[str]:
    """Parse 'Types of Metrics to Uncover' section into table format."""
    headers = ["Type", "Examples"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if this looks like a category heading
        if line and not line.endswith('.') and len(line) < 50 and i + 1 < len(section_lines):
            category = line
            i += 1
            examples = section_lines[i].strip() if i < len(section_lines) else ""
            if examples:
                rows.append([category, examples])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_strategies_table(section_lines: list[str]) -> list[str]:
    """Parse 'Strategies to Gain EB Access' section into table format."""
    headers = ["Strategy", "Description"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if this looks like a strategy heading
        if line and not line.endswith('.') and len(line) < 50 and i + 1 < len(section_lines):
            strategy = line
            i += 1
            description = section_lines[i].strip() if i < len(section_lines) else ""
            if description:
                rows.append([strategy, description])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_categories_of_decision_criteria_table(section_lines: list[str]) -> list[str]:
    """Parse 'Categories of Decision Criteria' section into table format."""
    headers = ["Category", "Examples"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if this looks like a category heading
        if line and not line.endswith('.') and len(line) < 50 and i + 1 < len(section_lines):
            category = line
            i += 1
            examples = section_lines[i].strip() if i < len(section_lines) else ""
            if examples:
                rows.append([category, examples])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_levels_of_pain_table(section_lines: list[str]) -> list[str]:
    """Parse 'Levels of Pain' section into table format."""
    headers = ["Level", "Description"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if line starts with "Level" pattern
        if line.startswith("Level ") and "—" in line and i < len(section_lines):
            level_desc = line.split("—", 1)
            if len(level_desc) == 2:
                i += 1
                description = section_lines[i].strip() if i < len(section_lines) else level_desc[1].strip()
                rows.append([level_desc[0].strip(), description])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_how_to_develop_champion_table(section_lines: list[str]) -> list[str]:
    """Parse 'How to Develop a Champion' section into table format."""
    headers = ["Action", "Description"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if this looks like an action heading
        if line and not line.endswith('.') and len(line) < 50 and i + 1 < len(section_lines):
            action = line
            i += 1
            description = section_lines[i].strip() if i < len(section_lines) else ""
            if description:
                rows.append([action, description])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_score_interpretation_table(section_lines: list[str]) -> list[str]:
    """Parse 'Score Interpretation' section into table format."""
    headers = ["Score Range", "Symbol", "Category", "Action"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Parse lines like "10–12  ✓  Commit"
        parts = line.split()
        if len(parts) >= 3 and ("–" in parts[0] or "-" in parts[0]):
            score_range = parts[0]
            symbol = parts[1]
            category = parts[2]
            i += 1
            action = section_lines[i].strip() if i < len(section_lines) else ""
            if action:
                rows.append([score_range, symbol, category, action])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_common_failures_table(section_lines: list[str]) -> list[str]:
    """Parse 'The 7 Most Common MEDDIC Failures' section into table format."""
    headers = ["#", "Failure", "Solution"]
    rows: list[list[str]] = []

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Parse lines like "#1  Single-threading"
        if line.startswith("#") and len(line) > 2:
            parts = line.split(None, 1)
            if len(parts) == 2:
                number = parts[0]
                failure = parts[1]
                i += 1
                solution = section_lines[i].strip() if i < len(section_lines) else ""
                if solution:
                    rows.append([number, failure, solution])
        i += 1

    return _build_markdown_table(headers, rows) if rows else []


def _parse_example_situation_questions_table(section_lines: list[str]) -> list[str]:
    """Parse 'Example Situation Questions' section for SPIN guide.

    Format: Each line is "Context Question text here?"
    Example: "Context How many people are currently in your sales organisation?"
    """
    headers = ["Context", "Question"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line or not line.endswith('?'):
            continue

        # Split on first question word
        for question_start in ['What ', 'How ', 'Who ', 'Where ', 'When ', 'Which ', 'Roughly ']:
            if question_start in line:
                parts = line.split(question_start, 1)
                if len(parts) == 2:
                    context = parts[0].strip()
                    question = question_start.strip() + ' ' + parts[1].strip()
                    if context and question:
                        rows.append([context, question])
                    break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_example_problem_questions_table(section_lines: list[str]) -> list[str]:
    """Parse 'Example Problem Questions' section for SPIN guide.

    Format: Each line is "PainArea Question text here?"
    """
    headers = ["Pain Area", "Example Problem Question"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line or not line.endswith('?'):
            continue

        # Split on first question word
        for question_start in ['How ', 'What ', 'Are ', 'Do ', 'Does ', 'Is ', 'Have ', 'Can ']:
            if question_start in line:
                parts = line.split(question_start, 1)
                if len(parts) == 2:
                    pain_area = parts[0].strip()
                    question = question_start.strip() + ' ' + parts[1].strip()
                    # Filter out lines that are headers or don't look like pain areas
                    if pain_area and question and len(pain_area.split()) <= 4:
                        rows.append([pain_area, question])
                    break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_how_implication_questions_work_table(section_lines: list[str]) -> list[str]:
    """Parse 'How Implication Questions Work' section for SPIN guide."""
    headers = ["Stage", "Question/Impact"]
    rows: list[list[str]] = []

    # Expected sequence: Problem identified, Implication #1, Implication #2, Implication #3, Effect on buyer
    stage_markers = [
        "Problem identified",
        "Implication #1",
        "Implication #2",
        "Implication #3",
        "Effect on buyer"
    ]

    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        # Check if line matches any stage marker
        for marker in stage_markers:
            if marker.lower() in line.lower():
                # Extract the content after the marker
                if marker in line:
                    content = line.replace(marker, "").strip()
                    rows.append([marker, content])
                elif i + 1 < len(section_lines):
                    i += 1
                    content = section_lines[i].strip()
                    rows.append([marker, content])
                break
        i += 1

    return _build_markdown_table(headers, rows) if rows and len(rows) >= 4 else []


def _parse_example_need_payoff_questions_table(section_lines: list[str]) -> list[str]:
    """Parse 'Example Need-Payoff Questions' section for SPIN guide.

    Format: Each line is "PainContext Question text here?"
    Example: "Ramp time If you could cut ramp time in half, how would..."
    """
    headers = ["After Pain Established", "Example Need-Payoff Question"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line or not line.endswith('?'):
            continue

        # Split on first question word (typically "If", "How", "What")
        for question_start in ['If ', 'How ', 'What ', 'Would ', 'Could ']:
            if question_start in line:
                parts = line.split(question_start, 1)
                if len(parts) == 2:
                    pain_context = parts[0].strip()
                    question = question_start.strip() + ' ' + parts[1].strip()
                    # Filter out lines that don't look like pain contexts
                    if pain_context and question and len(pain_context.split()) <= 4:
                        rows.append([pain_context, question])
                    break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_spin_common_mistakes_table(section_lines: list[str]) -> list[str]:
    """Parse 'The 8 Most Common SPIN Mistakes' section.

    Format: "#1 Mistake name Rest of description with Fix: advice"
    Example: "#1 Skipping straight to the pitch Sellers present...Fix: hold solution..."
    """
    headers = ["#", "Mistake", "Description & Fix"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        # Parse lines like "#1 Skipping straight to the pitch Sellers..."
        if not line.startswith("#") or len(line) < 5:
            continue

        # Extract number
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue

        number = parts[0]
        rest = parts[1]

        # Find where description starts (look for capital letter after lowercase or "Fix:")
        # Typically mistake is 2-5 words, then description starts
        words = rest.split()
        mistake_end_idx = 1

        # Look for clues where description starts
        for i in range(1, min(6, len(words))):
            word = words[i]
            # Description typically starts with a capital letter verb (Sellers, Asking, Showing, etc.)
            if i > 1 and word[0].isupper() and words[i-1][-1].islower():
                mistake_end_idx = i
                break

        mistake = ' '.join(words[:mistake_end_idx])
        description = ' '.join(words[mistake_end_idx:]) if mistake_end_idx < len(words) else ""

        if mistake and description:
            rows.append([number, mistake, description])

    return _build_markdown_table(headers, rows) if rows else []


def _parse_what_we_sell_table(section_lines: list[str]) -> list[str]:
    """Parse 'What We Sell' section for Sales Playbook.

    Format: "Product Description of the product..."
    """
    headers = ["Product", "Description"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # Known product names to look for
        products = ["Core Platform", "Accelerator", "Coaching Studio", "Professional Svcs"]

        for product in products:
            if line.startswith(product):
                description = line[len(product):].strip()
                if description:
                    rows.append([product, description])
                break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_primary_icp_table(section_lines: list[str]) -> list[str]:
    """Parse 'Primary ICP' section for Sales Playbook.

    Format: "Dimension Description of the dimension..."
    """
    headers = ["Dimension", "Description"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # Known ICP dimensions
        dimensions = ["Company Size", "Revenue", "Sales Org Size", "Segment",
                     "Geography", "Sales Motion", "Tech Stack", "Pain Triggers"]

        for dimension in dimensions:
            if line.startswith(dimension):
                description = line[len(dimension):].strip()
                if description:
                    rows.append([dimension, description])
                break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_meddic_acme_context_table(section_lines: list[str]) -> list[str]:
    """Parse 'MEDDIC in the Acme Context' section for Sales Playbook.

    Format: "Element Description specific to Acme..."
    """
    headers = ["MEDDIC Element", "Acme Context"]
    rows_by_element: dict[str, str] = {}

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # MEDDIC elements
        elements = ["Metrics", "Economic Buyer", "Decision Criteria",
                   "Decision Process", "Identify Pain", "Champion"]

        for element in elements:
            if not line.startswith(element):
                continue

            # Keep the first complete row per MEDDIC element and skip repeats.
            if element in rows_by_element:
                break

            context = line[len(element):].strip()
            if context:
                rows_by_element[element] = context
            break

    rows = [[element, rows_by_element[element]] for element in elements if element in rows_by_element]
    return _build_markdown_table(headers, rows) if rows else []


def _parse_discounting_guidelines_table(section_lines: list[str]) -> list[str]:
    """Parse 'Discounting Guidelines' section for Sales Playbook.

    Format: "Range Description and approval requirements..."
    """
    headers = ["Discount Range", "Approval & Guidelines"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # Discount ranges
        ranges = ["Up to 10%", "10–20%", "20–30%", "> 30%"]

        for discount_range in ranges:
            if line.startswith(discount_range):
                guidelines = line[len(discount_range):].strip()
                if guidelines:
                    rows.append([discount_range, guidelines])
                break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_mutual_close_plan_table(section_lines: list[str]) -> list[str]:
    """Parse 'The Mutual Close Plan' section for Sales Playbook.

    Format: "Component Description of what it contains..."
    """
    headers = ["Component", "Description"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # MCP components
        components = ["Goal State", "Milestones", "Dependencies",
                     "Success Metrics", "Escalation Path"]

        for component in components:
            if line.startswith(component):
                description = line[len(component):].strip()
                if description:
                    rows.append([component, description])
                break

    return _build_markdown_table(headers, rows) if rows else []


def _parse_compensation_structure_table(section_lines: list[str]) -> list[str]:
    """Parse 'Compensation Structure Overview' section for Sales Playbook.

    Format: "Component Description of compensation element..."
    """
    headers = ["Component", "Details"]
    rows: list[list[str]] = []

    for line in section_lines:
        line = line.strip()
        if not line:
            continue

        # Compensation components
        components = ["Base / Variable", "Accelerators", "Multi-year deals",
                     "SPIFs", "Clawbacks", "Ramp", "Commission", "Processing"]

        for component in components:
            if line.startswith(component):
                details = line[len(component):].strip()
                if details:
                    rows.append([component, details])
                break

    return _build_markdown_table(headers, rows) if rows else []


def _rewrite_known_table_sections(source_lines: list[str]) -> list[str]:
    table_configs = {
        # MEDDIC Guide tables
        "The Six Pillars at a Glance": {
            "stop_at": "How to Use This Guide",
            "parser": _parse_six_pillars_table,
        },
        "Types of Metrics to Uncover": {
            "stop_at": "Discovery Questions",
            "parser": _parse_types_of_metrics_table,
        },
        "Strategies to Gain EB Access": {
            "stop_at": "Red Flags",
            "parser": _parse_strategies_table,
        },
        "Categories of Decision Criteria": {
            "stop_at": "Discovery Questions",
            "parser": _parse_categories_of_decision_criteria_table,
        },
        "Levels of Pain": {
            "stop_at": "Pain vs. Problem vs. Implication",
            "parser": _parse_levels_of_pain_table,
        },
        "Champion vs. Coach vs. Sponsor": {
            "stop_at": "How to Identify a Champion",
            "parser": _parse_champion_table,
        },
        "How to Develop a Champion": {
            "stop_at": "Champion Testing Questions",
            "parser": _parse_how_to_develop_champion_table,
        },
        "Decision Process Mapping Template": {
            "stop_at": "Red Flags",
            "parser": _parse_decision_process_table,
        },
        "Scoring Rubric": {
            "stop_at": "Score Interpretation",
            "parser": _parse_scoring_rubric_table,
        },
        "Score Interpretation": {
            "stop_at": "Deal Review Agenda Template",
            "parser": _parse_score_interpretation_table,
        },
        "The 7 Most Common MEDDIC Failures": {
            "stop_at": "Best Practices by Sales Stage",
            "parser": _parse_common_failures_table,
        },
        "Best Practices by Sales Stage": {
            "stop_at": "Manager Coaching Reminders",
            "parser": _parse_best_practices_table,
        },
        # SPIN Guide tables
        "Example Situation Questions": {
            "stop_at": "Golden Rules for Situation Questions",
            "parser": _parse_example_situation_questions_table,
        },
        "Example Problem Questions": {
            "stop_at": "Crafting Strong Problem Questions",
            "parser": _parse_example_problem_questions_table,
        },
        "How Implication Questions Work": {
            "stop_at": "Example Implication Questions",
            "parser": _parse_how_implication_questions_work_table,
        },
        "Example Need-Payoff Questions": {
            "stop_at": "The Buyer-Articulation Principle",
            "parser": _parse_example_need_payoff_questions_table,
        },
        "The 8 Most Common SPIN Mistakes": {
            "stop_at": "Coaching Best Practices by Role",
            "parser": _parse_spin_common_mistakes_table,
        },
        # Sales Playbook tables
        "What We Sell": {
            "stop_at": "Our Positioning",
            "parser": _parse_what_we_sell_table,
        },
        "Primary ICP": {
            "stop_at": "Buyer Personas",
            "parser": _parse_primary_icp_table,
        },
        "MEDDIC in the Acme Context": {
            "stop_at": "Discovery Question Bank",
            "parser": _parse_meddic_acme_context_table,
        },
        "Discounting Guidelines": {
            "stop_at": "Proposal Best Practices",
            "parser": _parse_discounting_guidelines_table,
        },
        "The Mutual Close Plan": {
            "stop_at": "Negotiation Principles",
            "parser": _parse_mutual_close_plan_table,
        },
        "Compensation Structure Overview": {
            "stop_at": "Onboarding & Ramp Expectations",
            "parser": _parse_compensation_structure_table,
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

    # Drop repeated guide title footer artifacts
    if "meddic sales methodology guide" in lowered or "salescoach ai" in lowered:
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





