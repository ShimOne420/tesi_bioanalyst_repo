from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def check_path(label: str, raw_value: str | None) -> tuple[bool, str]:
    if not raw_value:
        return False, f"{label}: variabile non impostata"
    path = Path(raw_value)
    if path.exists():
        return True, f"{label}: OK -> {path}"
    return False, f"{label}: path non trovato -> {path}"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(env_path)

    checks = [
        check_path("BIOCUBE_DIR", os.getenv("BIOCUBE_DIR")),
        check_path("BIOANALYST_MODEL_DIR", os.getenv("BIOANALYST_MODEL_DIR")),
        check_path("PROJECT_OUTPUT_DIR", os.getenv("PROJECT_OUTPUT_DIR")),
    ]

    print(f"PROJECT_ROOT: {project_root}")
    print(f".env: {'OK' if env_path.exists() else 'MANCANTE'} -> {env_path}")
    print()

    ok = True
    for success, message in checks:
        print(message)
        ok = ok and success

    print()
    if ok:
        print("Setup base pronto.")
        return 0

    print("Setup incompleto: controlla i path sopra.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
