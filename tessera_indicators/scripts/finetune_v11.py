#!/usr/bin/env python3
"""Fine-tune a TESSERA v1.1 MPC inference encoder on labelled target supports.

The index is JSONL with `tile_path`, `pixel_indices`, `target_value`, `split`,
and `sample_id`. Representations are pooled per target support, so the runner
does not upsample a coarse indicator raster to 10 m.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tessera-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config-json", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--task", choices=("bii", "msa_globio4"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--unfreeze-backbones", action="store_true")
    args = parser.parse_args()
    import torch
    from torch import nn

    source = Path(args.tessera_root) / "tessera_infer_QAT" / "src"
    if not source.is_dir() or not Path(args.checkpoint).is_file():
        raise FileNotFoundError("Expected official Tessera checkout and v1.1 MPC full checkpoint.")
    sys.path.insert(0, str(source))
    from models.ssl_model_v1_1 import build_v1_1_inference_model, load_v1_1_checkpoint
    from datasets.ssl_dataset_v1_1 import SingleTileInferenceDatasetV1_1

    config = json.loads(Path(args.config_json).read_text(encoding="utf-8"))
    if config.get("data_source") != "mpc":
        raise ValueError("This planned critical path requires the MPC checkpoint and MPC normalisation.")
    records = [json.loads(line) for line in Path(args.index).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records or any(record.get("split") not in {"train", "validation", "test"} or not record.get("pixel_indices") for record in records):
        raise ValueError("Index must contain non-empty train/validation/test labelled records.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("True fine-tuning is intentionally CUDA-only for this delivery path.")
    encoder = build_v1_1_inference_model(config, device)
    missing, unexpected, checkpoint_config = load_v1_1_checkpoint(encoder, args.checkpoint)
    if missing or unexpected:
        raise RuntimeError(f"Checkpoint/model mismatch: missing={missing}, unexpected={unexpected}")
    for parameter in encoder.parameters():
        parameter.requires_grad = args.unfreeze_backbones
    for parameter in encoder.dim_reducer.parameters():
        parameter.requires_grad = True
    head = nn.Sequential(nn.LayerNorm(config.get("representation_dim", 192)), nn.Linear(config.get("representation_dim", 192), 1)).to(device)
    optimizer = torch.optim.AdamW([parameter for parameter in list(encoder.parameters()) + list(head.parameters()) if parameter.requires_grad], lr=args.learning_rate)
    by_tile: dict[str, object] = {}
    losses = []
    train = [record for record in records if record["split"] == "train"]
    for _epoch in range(args.epochs):
        encoder.train(); head.train()
        for record in train:
            dataset = by_tile.setdefault(record["tile_path"], SingleTileInferenceDatasetV1_1(record["tile_path"], config))
            representations = []
            for pixel_index in record["pixel_indices"]:
                item = dataset[int(pixel_index)]
                s2 = item["s2"].unsqueeze(0).to(device)
                s1 = item["s1"].unsqueeze(0).to(device)
                representations.append(encoder(s2, s1))
            target = torch.tensor([[float(record["target_value"])]], device=device)
            pooled = torch.cat(representations, dim=0).mean(dim=0, keepdim=True)
            prediction = torch.sigmoid(head(pooled))
            loss = torch.nn.functional.mse_loss(prediction, target)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            losses.append(float(loss.detach().cpu()))
    destination = Path(args.output); destination.mkdir(parents=True, exist_ok=True)
    torch.save({"encoder": encoder.state_dict(), "head": head.state_dict(), "task": args.task, "config": config}, destination / "checkpoint.pt")
    write_json(destination / "run_manifest.json", {"task": args.task, "checkpoint": str(Path(args.checkpoint).resolve()), "tessera_root": str(Path(args.tessera_root).resolve()), "device": str(device), "epochs": args.epochs, "unfreeze_backbones": args.unfreeze_backbones, "mean_train_loss": float(np.mean(losses)), "checkpoint_config": checkpoint_config})


if __name__ == "__main__":
    main()
