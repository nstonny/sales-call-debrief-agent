"""Stop hook: runs the test suite at the end of every turn and surfaces a
visible message only when something is broken.

Non-blocking by design: this never forces Claude to keep working (no
"decision": "block" in the JSON output, and it always exits 0). A failure is
surfaced to the user via systemMessage so it can't be missed, but the turn
ends normally -- there is no auto-retry loop, and a pre-existing or unrelated
failure will never strand Claude unable to stop.

Silent on success, matching the other hooks in this repo: the suite runs in
roughly 5-7 seconds offline, and printing a confirmation on every single turn
(including turns that touched no code) would be noise, not signal.
"""

import json
import re
import subprocess
import sys

SUMMARY_RE = re.compile(r"\d+\s+(passed|failed|error|skipped)")


def _extract_summary(output: str) -> str:
    for line in reversed(output.splitlines()):
        if SUMMARY_RE.search(line):
            return line.strip().strip("=").strip()
    return "pytest exited non-zero (see `uv run pytest` for details)"


def _emit(message: str) -> None:
    print(json.dumps({"systemMessage": message}))


def main() -> None:
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        _emit("Test suite timed out after 120s -- run `uv run pytest` to investigate.")
        sys.exit(0)
    except Exception as exc:
        _emit(f"Could not run the test suite: {exc}")
        sys.exit(0)

    if result.returncode == 0:
        sys.exit(0)

    summary = _extract_summary((result.stdout or "") + (result.stderr or ""))
    _emit(f"⚠️ Tests failing: {summary}. Run `uv run pytest` for details.")
    sys.exit(0)


if __name__ == "__main__":
    main()
