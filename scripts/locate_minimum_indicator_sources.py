from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PATTERNS = {
    "species": ["species", "occurrence", ".parquet"],
    "temperature": ["t2m", "temperature", "2m_temperature"],
    "precipitation": ["tp", "precip", "total_precipitation"],
}


def score_match(path_str: str, tokens: list[str]) -> int:
    lowered = path_str.lower()
    return sum(1 for token in tokens if token.lower() in lowered)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    biocube_dir_raw = os.getenv("BIOCUBE_DIR")
    if not biocube_dir_raw:
        raise SystemExit("BIOCUBE_DIR non impostata in .env")

    biocube_dir = Path(biocube_dir_raw)
    if not biocube_dir.exists():
        raise SystemExit(f"BIOCUBE_DIR non esiste: {biocube_dir}")

    all_files = [p for p in biocube_dir.rglob("*") if p.is_file()]

    for label, tokens in PATTERNS.items():
        print(f"[{label}]")
        scored = []
        for path in all_files:
            score = score_match(str(path), tokens)
            if score > 0:
                scored.append((score, path))

        scored.sort(key=lambda item: (-item[0], str(item[1])))

        if not scored:
            print("- nessun candidato trovato al momento")
            print()
            continue

        for score, path in scored[:20]:
            print(f"- score={score} -> {path}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
