"""Run the required local release gates; stop at the first failure."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        ("Installed dependency consistency", ROOT, ["-m", "pip", "check"]),
        ("Credential hygiene", ROOT, ["scripts/check_secrets.py"]),
        ("Django system checks", ROOT / "backend", ["manage.py", "check"]),
        ("Migration consistency", ROOT / "backend", ["manage.py", "makemigrations", "--check", "--dry-run"]),
        ("Backend regression and Sprint 7 integration", ROOT / "backend", ["manage.py", "test"]),
        ("Frontend and API integration", ROOT / "frontend", ["-m", "pytest", "-v", "--durations=10"]),
        ("Fresh database and server startup", ROOT, ["scripts/smoke_start.py"]),
    ]
    for label, directory, arguments in checks:
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run([sys.executable, *arguments], cwd=directory)
        if result.returncode:
            print(f"Release gate failed: {label}. Do not promote this candidate.", file=sys.stderr)
            return result.returncode
    print("\nAll local release gates passed. Review the exact GitHub candidate before promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
