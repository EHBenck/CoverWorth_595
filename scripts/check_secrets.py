"""Focused release check: private environment files and literal eBay credentials.

Reports filenames and line numbers only, never credential values. This checks
candidate files, not every possible secret format or the repository's history.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_KEYS = {"EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_ACCESS_TOKEN"}
PRODUCTION_ID = re.compile(r"[A-Za-z0-9-]+-PRD-[A-Za-z0-9-]{16,}")
ENV_VALUE = re.compile(r"^\s*(EBAY_CLIENT_ID|EBAY_CLIENT_SECRET|EBAY_ACCESS_TOKEN)\s*=\s*(.*?)\s*$")


def literal_value(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def target_key(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return literal_value(node.slice)
    return None


def main() -> int:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    issues = set()
    for raw in set(listed.stdout.split(b"\0")):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape")
        path = ROOT / relative
        name = path.name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example") or name.endswith(".env"):
            issues.add((relative, 0, "private environment file is included"))
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for number, line in enumerate(source.splitlines(), 1):
            if PRODUCTION_ID.search(line):
                issues.add((relative, number, "possible literal eBay production credential"))
            if name == ".env.example":
                match = ENV_VALUE.match(line)
                if match and match.group(2).strip('"\''):
                    issues.add((relative, number, "eBay example value must be blank"))
        if path.suffix != ".py":
            continue
        try:
            parsed = ast.parse(source)
        except SyntaxError:
            continue  # Django/pytest/compile checks report invalid Python separately.
        for node in ast.walk(parsed):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = literal_value(node.value)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if value and any(target_key(target) in SENSITIVE_KEYS for target in targets):
                    issues.add((relative, node.lineno, "literal eBay credential assignment"))
            elif isinstance(node, ast.Dict):
                for key, value_node in zip(node.keys, node.values):
                    if literal_value(key) in SENSITIVE_KEYS and literal_value(value_node):
                        issues.add((relative, node.lineno, "literal eBay credential in dictionary"))
    for path, line, reason in sorted(issues):
        print(f"FAIL: {path}{':' + str(line) if line else ''}: {reason}")
    if issues:
        return 1
    print("PASS: no private environment files or recognized literal eBay credentials in candidate files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
