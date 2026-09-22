# TESSERA biodiversity indicators

This module implements the reproducible research path for two separate
TESSERA v1.1 MPC regression tasks: Biodiversity Intactness Index (`bii`) and
GLOBIO 4 Mean Species Abundance (`msa_globio4`). It deliberately does not
modify the existing BioAnalyst observed/forecast pipeline.

## Status and boundary

The code is ready to validate sources, prepare spatially independent samples,
train a frozen-embedding Ridge baseline, evaluate predictions, and construct a
BioMAP-compatible report context. Fine-tuning is an executable PyTorch runner
once the official TESSERA checkout, the full v1.1 MPC checkpoint, target maps,
and preprocessed Sentinel tiles are mounted locally. It refuses to run with
missing or inconsistent assets rather than generating a misleading model.

## Layout

- `config/tasks.json` is the single source of truth for target provenance.
- `src/tessera_indicators/` holds contracts, spatial split logic, and metrics.
- `scripts/` exposes the command-line workflow.
- `artifacts/` is created at runtime and is ignored by Git.

## Workflow

```bash
python scripts/preflight.py --config config/tasks.json
python scripts/make_spatial_splits.py --input prepared/samples.parquet --output prepared/samples_split.parquet
python scripts/train_frozen_baseline.py --input prepared/samples_split.parquet --task bii --output artifacts/bii/frozen
python scripts/evaluate_predictions.py --input artifacts/bii/frozen/predictions.csv --output artifacts/bii/frozen/metrics.json
python scripts/build_report_context.py --task bii --metrics artifacts/bii/frozen/metrics.json --output artifacts/bii/report_context.json
```

Prepared sample tables require `sample_id`, `longitude`, `latitude`,
`target_value`, `coverage_fraction`, and feature columns named `emb_*`. They
may optionally include `region`, `target_year`, and `target_version`. Target
values must stay in `[0, 1]`; coarse target values are represented once per
target support, never copied blindly to every 10 m pixel.

## Fine-tuning gate

`scripts/finetune_v11.py` accepts a JSONL index of labelled target supports and
loads the official v1.1 inference model plus the *full MPC checkpoint*. It
optimises a task-specific regression head and unfrozen `dim_reducer` by
default. Each record provides `tile_path` and `pixel_indices`; the encoder
representations are pooled before loss. `--unfreeze-backbones` is intentionally opt-in after a validated
baseline. Use a Linux CUDA environment; the runner records all paths and
versions in its run manifest.
