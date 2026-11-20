"""Check prerequisites that pip check alone cannot enforce."""

from importlib.metadata import PackageNotFoundError, version
import sys

PINNED = {
    "Django": "6.1.1",
    "nicegui": "3.18.0",
}


def main() -> int:
    failed = False
    # Python 3.12 is the repo's CI/release target. Other versions may work,
    # but they have not been verified against this exact dependency set.
    if sys.version_info[:2] != (3, 12):
        print(f"FAIL: Python 3.12 required for the release gate; found {sys.version.split()[0]}.")
        failed = True
    for name, expected in PINNED.items():
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = "not installed"
        if installed == expected:
            print(f"PASS: {name}=={expected}")
        else:
            print(f"FAIL: {name}=={expected} is required; found {installed}.")
            failed = True
    if failed:
        print("Create a Python 3.12 venv and run: python -m pip install -r frontend/requirements.txt")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
