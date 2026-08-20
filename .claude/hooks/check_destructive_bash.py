"""PreToolUse guard on the Bash tool: blocks a curated set of destructive
commands before they run.

Reads the hook's stdin JSON (tool_input.command), splits it into segments on
shell operators (&&, ||, ;, |), and checks each segment against the patterns
below. Exit 2 blocks the tool call and surfaces the printed reason; exit 0
lets it through.

This is a guard rail against accidental self-inflicted damage, not a security
boundary: it inspects the literal command text, so it can be defeated by
variable indirection, aliases, or writing an equivalent command a different
way. It also only gates Claude Code's Bash tool -- a command run outside
Claude Code is unaffected.

The pattern list mirrors the destructive-git-command list already named in
the project's standing git safety guidance (push --force, reset --hard,
checkout ., restore ., clean -f, branch -D), plus rm -rf.

There is deliberately no override flag: if a blocked command is genuinely
intended, run it outside Claude Code, or edit this file.
"""

import json
import shlex
import sys


def _load_command() -> str | None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return None
    return (data.get("tool_input") or {}).get("command")


def _split_segments(command: str) -> list[list[str]]:
    """Tokenize and split on shell operators, so `a && rm -rf b` is still caught."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes etc: this is a guard rail, not a shell parser -- fail open.
        return []

    operators = {"&&", "||", ";", "|", "&", "(", ")"}
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in operators:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def _strip_sudo(seg: list[str]) -> list[str]:
    return seg[1:] if seg and seg[0] == "sudo" else seg


def _is_git(seg: list[str], *subcommands: str) -> bool:
    seg = _strip_sudo(seg)
    return len(seg) >= 2 and seg[0] == "git" and seg[1] in subcommands


def _has_flag(seg: list[str], *long_or_exact: str) -> bool:
    return any(tok in long_or_exact for tok in seg)


def _has_short_char(seg: list[str], char: str) -> bool:
    return any(tok.startswith("-") and not tok.startswith("--") and char in tok[1:] for tok in seg)


def check_rm_rf(seg: list[str]) -> str | None:
    seg = _strip_sudo(seg)
    if not seg or seg[0].rsplit("/", 1)[-1] != "rm":
        return None
    force = _has_flag(seg, "-f", "--force") or _has_short_char(seg, "f")
    recursive = (
        _has_flag(seg, "-r", "-R", "--recursive")
        or _has_short_char(seg, "r")
        or _has_short_char(seg, "R")
    )
    if force and recursive:
        return "rm -rf (or equivalent) recursively force-deletes with no confirmation and no undo."
    return None


def check_force_push(seg: list[str]) -> str | None:
    if not _is_git(seg, "push"):
        return None
    # --force-with-lease / --force-if-includes are the safer forms and are
    # deliberately not caught here -- they are different tokens from -f/--force.
    if _has_flag(seg, "-f", "--force"):
        return "git push --force can overwrite remote history other people rely on."
    return None


def check_reset_hard(seg: list[str]) -> str | None:
    if not _is_git(seg, "reset"):
        return None
    if "--hard" in seg:
        return "git reset --hard discards uncommitted changes with no recovery path."
    return None


def check_checkout_dot(seg: list[str]) -> str | None:
    if not _is_git(seg, "checkout"):
        return None
    if "." in seg:
        return "git checkout . discards every uncommitted working-tree change."
    return None


def check_restore_worktree(seg: list[str]) -> str | None:
    if not _is_git(seg, "restore"):
        return None
    if "." not in seg:
        return None
    if "--staged" in seg and "--worktree" not in seg:
        return None  # unstages only, does not discard file content
    return "git restore . discards uncommitted working-tree changes."


def check_clean_force(seg: list[str]) -> str | None:
    if not _is_git(seg, "clean"):
        return None
    if _has_flag(seg, "-f", "--force") or _has_short_char(seg, "f"):
        return "git clean -f permanently deletes untracked files."
    return None


def check_branch_force_delete(seg: list[str]) -> str | None:
    if not _is_git(seg, "branch"):
        return None
    if _has_flag(seg, "-D") or _has_short_char(seg, "D"):
        return "git branch -D force-deletes a branch, discarding any unmerged commits."
    if "--delete" in seg and (_has_flag(seg, "-f", "--force") or _has_short_char(seg, "f")):
        return "git branch --delete --force discards any unmerged commits."
    return None


CHECKS = (
    check_rm_rf,
    check_force_push,
    check_reset_hard,
    check_checkout_dot,
    check_restore_worktree,
    check_clean_force,
    check_branch_force_delete,
)


def main() -> None:
    command = _load_command()
    if not command:
        sys.exit(0)

    for segment in _split_segments(command):
        for check in CHECKS:
            reason = check(segment)
            if reason:
                print(f"Blocked: {' '.join(segment)}", file=sys.stderr)
                print(reason, file=sys.stderr)
                print(
                    "If this is genuinely intended, run it yourself outside Claude Code.",
                    file=sys.stderr,
                )
                sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
