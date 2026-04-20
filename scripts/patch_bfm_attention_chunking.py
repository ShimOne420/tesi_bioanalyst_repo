#!/usr/bin/env python3
"""Applica una patch locale per ridurre la memoria dell'attenzione BioAnalyst.

La patch modifica solo il repo esterno `external/bfm-model`: su CUDA usa lo
stesso calcolo di attenzione, ma processa le query a blocchi quando la sequenza
e lunga. Serve per evitare allocazioni giganti su GPU con VRAM limitata.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPERS_PATH = PROJECT_ROOT / "external" / "bfm-model" / "bfm_model" / "perceiver_components" / "helpers.py"


ORIGINAL_IMPORT = "import weakref\n"
PATCHED_IMPORT = "import os\nimport weakref\n"

ORIGINAL_BLOCK = '''        # MPS can over-allocate buffers on long-sequence attention. We keep the
        # exact same attention semantics, but run it in smaller query chunks on
        # Apple GPU to avoid the invalid giant buffer request.
        if q.device.type == "mps":
            if self.n_kv_heads < self.n_q_heads:
                repeat_factor = self.n_q_heads // self.n_kv_heads
                k = k.repeat_interleave(repeat_factor, dim=1)
                v = v.repeat_interleave(repeat_factor, dim=1)

            chunk_size = 64
'''

PATCHED_BLOCK = '''        # Su sequenze lunghe alcune build CUDA possono materializzare la matrice
        # attenzione completa. Il chunking mantiene la stessa semantica, ma limita
        # la memoria processando blocchi di query.
        chunk_size = int(os.getenv("BFM_ATTENTION_CHUNK_SIZE", "64"))
        use_chunked_attention = q.device.type == "mps" or (q.device.type == "cuda" and seq_len_q > chunk_size)
        if use_chunked_attention:
            if self.n_kv_heads < self.n_q_heads:
                repeat_factor = self.n_q_heads // self.n_kv_heads
                k = k.repeat_interleave(repeat_factor, dim=1)
                v = v.repeat_interleave(repeat_factor, dim=1)

'''


def main() -> None:
    if not HELPERS_PATH.exists():
        raise SystemExit(f"File non trovato: {HELPERS_PATH}")

    text = HELPERS_PATH.read_text(encoding="utf-8")
    changed = False

    if PATCHED_BLOCK in text:
        print("Patch attenzione gia presente.")
    elif ORIGINAL_BLOCK in text:
        text = text.replace(ORIGINAL_BLOCK, PATCHED_BLOCK)
        changed = True
    else:
        raise SystemExit("Blocco attenzione atteso non trovato. Controllare la versione di external/bfm-model.")

    if PATCHED_IMPORT not in text:
        if ORIGINAL_IMPORT not in text:
            raise SystemExit("Import `weakref` non trovato. Patch import non applicabile.")
        text = text.replace(ORIGINAL_IMPORT, PATCHED_IMPORT, 1)
        changed = True

    if changed:
        HELPERS_PATH.write_text(text, encoding="utf-8")
        print(f"Patch applicata: {HELPERS_PATH}")
    else:
        print(f"Nessuna modifica necessaria: {HELPERS_PATH}")


if __name__ == "__main__":
    main()
