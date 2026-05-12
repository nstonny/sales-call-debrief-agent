from pathlib import Path

# Use shared rubric files under src/data/rubrics.
RUBRICS_DIR = Path(__file__).resolve().parents[2] / "data" / "rubrics"


def load_rubric_text(rubric_names: list[str] | None) -> str:
    """
    Load one or more rubric text files from src/data/rubrics/.

    Accepts names with or without .txt extension.
    Returns one combined text block for system-prompt injection.
    """
    if not rubric_names:
        return ""

    base_dir = RUBRICS_DIR.resolve()
    blocks: list[str] = []

    for raw_name in rubric_names:
        name = raw_name.strip()
        if not name:
            continue

        filename = name if name.endswith(".txt") else f"{name}.txt"
        path = (base_dir / filename).resolve()

        # Prevent path traversal to keep file loading restricted to src/data/rubrics.
        if path.parent != base_dir:
            raise ValueError(f"Invalid rubric name: {raw_name}")

        if not path.exists():
            raise FileNotFoundError(f"Rubric file not found: {filename}")

        content = path.read_text(encoding="utf-8").strip()
        if content:
            blocks.append(f"[Rubric: {filename}]\n{content}")

    return "\n\n".join(blocks)
