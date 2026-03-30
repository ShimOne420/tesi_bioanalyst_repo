from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    biocube_dir_raw = os.getenv("BIOCUBE_DIR")
    if not biocube_dir_raw:
        raise SystemExit("BIOCUBE_DIR non impostata in .env")

    biocube_dir = Path(biocube_dir_raw)
    if not biocube_dir.exists():
        raise SystemExit(f"BIOCUBE_DIR non esiste: {biocube_dir}")

    file_counter: Counter[str] = Counter()
    total_size = 0
    incomplete = []
    locks = []
    sample_files: list[Path] = []

    for path in biocube_dir.rglob("*"):
        if path.is_file():
            suffix = path.suffix.lower() or "<none>"
            file_counter[suffix] += 1
            try:
                total_size += path.stat().st_size
            except OSError:
                pass
            if path.name.endswith(".incomplete"):
                incomplete.append(path)
            if path.name.endswith(".lock"):
                locks.append(path)
            if len(sample_files) < 20:
                sample_files.append(path)

    print(f"BIOCUBE_DIR: {biocube_dir}")
    print(f"Dimensione corrente: {human_size(total_size)}")
    print()

    top_level = sorted(p.name for p in biocube_dir.iterdir())
    print("Contenuto top-level:")
    for name in top_level:
        print(f"- {name}")
    print()

    print("Estensioni rilevate:")
    for suffix, count in file_counter.most_common():
        print(f"- {suffix}: {count}")
    print()

    print("Esempi di file:")
    for path in sample_files:
        print(f"- {path}")
    print()

    print(f"File .incomplete: {len(incomplete)}")
    for path in incomplete[:10]:
        print(f"- {path}")
    print()

    print(f"File .lock: {len(locks)}")
    for path in locks[:10]:
        print(f"- {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
